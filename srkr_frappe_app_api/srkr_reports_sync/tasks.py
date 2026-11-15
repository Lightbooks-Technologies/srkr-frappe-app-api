# Refresh jobs for the srkr_reports summary schema (read by the external
# srkr-academics-portal). Frappe/MariaDB stays the single source of truth —
# these jobs only aggregate FROM tab* INTO srkr_reports.rpt_*.
#
# Registered in hooks.py scheduler_events:
#   - incremental_refresh: cron tick, self-throttled to about hourly. It
#     recalculates only the summary rows whose attendance changed since the
#     last run (see _changed_scope); a full-term rebuild is the fallback.
#   - nightly_full_rebuild: cron 2 AM (also reconciles hard deletes via
#     tabDeleted Document — incremental-on-modified cannot see deletes)
#
# The denominator rules (docstatus=1, schedule_date <= today, sibling groups,
# per-term first-year floor from srkr_reports.cfg_term_settings) live in the
# aggregation SQL below and NOWHERE else. Change them only with Dean sign-off.

import datetime
import json

import frappe

REPORTS_SCHEMA = "srkr_reports"
LAST_RUN_KEY = "srkr_reports_sync_last_run"

# Teachers mark attendance in the first minutes of a period. The incremental
# job is scheduled every 5 min but self-throttles: it never starts inside a
# period's marking window, never starts if it would still be running when
# the next period begins, and runs at most about once an hour.
ATTENDANCE_GRACE_MIN = 15   # quiet window after every class start (timetable-driven)
RUN_BUDGET_MIN = 5          # longest a refresh run is expected to take
MIN_INTERVAL_MIN = 55       # effective cadence ~hourly

# Changed-only refresh. A normal hour changes a few thousand attendance rows
# on one to a few dates; anything far beyond that is a backfill, and one
# full-term rebuild is then simpler and no slower.
CHANGE_OVERLAP_MIN = 15     # re-read this much before the last run (late commits)
MAX_CHANGED_ROWS = 50000
MAX_CHANGED_DAYS = 3000     # (student group, date) rows of rpt_group_course_day
MAX_CHANGED_DATES = 31
GROUPS_TEXT_LIMIT = 500     # rpt_student_course_term.student_groups is cut at this length
TMP_PAIRS = "_tmp_rpt_pairs"
TMP_SLICES = "_tmp_rpt_slices"
TMP_DAYS = "_tmp_rpt_days"


def _as_time(value) -> datetime.time:
    """`tabCourse Schedule.from_time` comes back as timedelta from the driver."""
    if isinstance(value, datetime.timedelta):
        return (datetime.datetime.min + value).time()
    if isinstance(value, datetime.datetime):
        return value.time()
    if isinstance(value, str):
        return datetime.time.fromisoformat(value[:8])
    return value


def _refresh_allowed_now() -> bool:
    now = frappe.utils.now_datetime()  # site timezone, same as the timetable
    last_run = frappe.db.get_global(LAST_RUN_KEY)
    if last_run:
        age = (now - frappe.utils.get_datetime(last_run)).total_seconds()
        if age < MIN_INTERVAL_MIN * 60:
            return False
    starts = frappe.db.sql(
        """
        SELECT DISTINCT from_time FROM `tabCourse Schedule`
        WHERE schedule_date = %(today)s AND from_time IS NOT NULL
        """,
        {"today": now.date()},
        as_list=True,
    )
    grace = datetime.timedelta(minutes=ATTENDANCE_GRACE_MIN)
    budget = datetime.timedelta(minutes=RUN_BUDGET_MIN)
    for (from_time,) in starts:
        start = datetime.datetime.combine(now.date(), _as_time(from_time))
        if start <= now < start + grace:
            return False  # a class just started: teachers are marking now
        if now < start < now + budget:
            return False  # we'd still be running when that class starts
    return True


def _non_locking_reads():
    """Make the REPLACE ... SELECT aggregations read without locking.

    Under InnoDB's default REPEATABLE READ, INSERT/REPLACE ... SELECT takes a
    shared next-key lock on EVERY source row it reads and holds it until the
    transaction commits. For a term that is ~2.4M `tabStudent Attendance` rows
    (observed 2026-10-14: 7.3M row locks held for ~4 min by one refresh run),
    which blocks every teacher's attendance INSERT/UPDATE during the run ->
    "Lock wait timeout exceeded" after 50s -> ALB 504 -> "Submission Failed"
    on the instructor app. Dozens of classes went unmarked per day.

    READ COMMITTED makes the SELECT side a consistent (non-locking) read;
    the REPLACE still locks only the target rpt_* rows, which nothing else
    writes. Session-scoped: the scheduler worker opens a fresh connection per
    job, and we restore the default on exit anyway.
    """
    # The level applies to the NEXT transaction; Frappe runs with autocommit
    # off, so end the one the preceding SELECTs opened first.
    frappe.db.commit()
    frappe.db.sql("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
    # Frappe's commit() opens the next transaction straight away, so the SET
    # above landed inside one that still has the old level. Without this second
    # commit the first REPLACE ran under REPEATABLE READ and locked every row
    # it read (seen on prod 2026-11-15: 5.8M row locks held for ~2 minutes).
    frappe.db.commit()


def _default_isolation():
    frappe.db.commit()
    frappe.db.sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    frappe.db.commit()

# Terms are auto-discovered: any academic term that has submitted attendance.
ACTIVE_TERMS_SQL = """
    SELECT DISTINCT sg.academic_term
    FROM `tabStudent Group` sg
    JOIN `tabStudent Attendance` sa
      ON sa.student_group = sg.name AND sa.docstatus = 1
    WHERE sg.academic_term IS NOT NULL
"""


def _rebuild_term_student_course(term: str, changed_only: bool = False):
    # changed_only: read only the classes of the (student group, course)
    # slices in _tmp_rpt_slices and keep only the (student, course) pairs in
    # _tmp_rpt_pairs. The slices hold every group a pair has attendance in,
    # so each pair is still summed over all of its rows.
    source = (
        f"""{TMP_SLICES} sl
        JOIN `tabCourse Schedule` cs
          ON cs.student_group = sl.student_group AND cs.course = sl.course
        JOIN `tabStudent Attendance` sa ON sa.course_schedule = cs.name
        JOIN {TMP_PAIRS} tp ON tp.student = sa.student AND tp.course = cs.course"""
        if changed_only
        else """`tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule"""
    )
    frappe.db.sql(
        f"""
        REPLACE INTO {REPORTS_SCHEMA}.rpt_student_course_term
          (academic_year, academic_term, program, program_semester, student_groups,
           student, student_name, custom_student_id, course, course_name, department,
           present_count, absent_count, classes_held, attendance_pct, last_refreshed)
        SELECT
          sg_meta.academic_year, %(term)s,
          MAX(sg_meta.program), MAX(sg_meta.program_semester),
          LEFT(GROUP_CONCAT(DISTINCT cs.student_group), 500),
          sa.student, MAX(sa.student_name), st.custom_student_id,
          cs.course, c.course_name, MAX(p.department),
          SUM(sa.status = 'Present'), SUM(sa.status = 'Absent'), COUNT(*),
          ROUND(SUM(sa.status = 'Present') / COUNT(*) * 100, 2), NOW()
        FROM {source}
        JOIN `tabCourse` c           ON c.name = cs.course
        JOIN `tabStudent Group` sg_meta ON sg_meta.name = cs.student_group
        JOIN `tabProgram` p          ON p.name = sg_meta.program
        LEFT JOIN `tabStudent` st    ON st.name = sa.student
        LEFT JOIN {REPORTS_SCHEMA}.cfg_term_settings cfg
               ON cfg.academic_term = %(term)s
        WHERE sa.docstatus = 1
          AND cs.schedule_date <= CURDATE()
          AND sg_meta.academic_term = %(term)s
          AND (
            cs.student_group NOT REGEXP 'SEM-0[12]'
            OR cfg.first_year_attendance_start IS NULL
            OR sa.date >= cfg.first_year_attendance_start
          )
        GROUP BY sg_meta.academic_year, sa.student,
                 st.custom_student_id, cs.course, c.course_name
        """,
        {"term": term},
    )


def _rebuild_term_group_course_day(term: str, changed_only: bool = False):
    # changed_only: only the (student group, date) days in _tmp_rpt_days,
    # each recalculated from all of that day's rows for the group.
    scope = (
        f"""JOIN {TMP_DAYS} td
          ON td.student_group = sa.student_group AND td.att_date = sa.date"""
        if changed_only
        else ""
    )
    frappe.db.sql(
        f"""
        REPLACE INTO {REPORTS_SCHEMA}.rpt_group_course_day
          (academic_year, academic_term, department, program, student_group, course,
           course_name, schedule_date, present_count, absent_count, class_held,
           instructor, last_refreshed)
        SELECT
          sg.academic_year, %(term)s, p.department, sg.program, sa.student_group,
          cs.course, c.course_name, sa.date,
          SUM(sa.status = 'Present'), SUM(sa.status = 'Absent'), 1,
          MAX(cs.instructor), NOW()
        FROM `tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
        JOIN `tabCourse` c           ON c.name = cs.course
        JOIN `tabStudent Group` sg   ON sg.name = sa.student_group
        JOIN `tabProgram` p          ON p.name = sg.program
        {scope}
        WHERE sa.docstatus = 1
          AND sg.academic_term = %(term)s
        GROUP BY sg.academic_year, p.department, sg.program,
                 sa.student_group, cs.course, c.course_name, sa.date
        """,
        {"term": term},
    )


def _rebuild_term_dept_day(term: str, dates=None):
    # dates: only these schedule dates, each recalculated in full for every
    # department. None = the whole term.
    scope = "AND cs.schedule_date IN %(dates)s" if dates else ""
    frappe.db.sql(
        f"""
        REPLACE INTO {REPORTS_SCHEMA}.rpt_dept_term_day
          (department, academic_year, academic_term, schedule_date, classes_scheduled,
           classes_marked, students_present, students_absent, attendance_pct,
           last_refreshed)
        SELECT
          p.department, sg.academic_year, %(term)s, cs.schedule_date,
          COUNT(DISTINCT cs.name), COUNT(DISTINCT sa.course_schedule),
          COALESCE(SUM(sa.status = 'Present'), 0),
          COALESCE(SUM(sa.status = 'Absent'), 0),
          ROUND(SUM(sa.status = 'Present') / NULLIF(COUNT(sa.name), 0) * 100, 2),
          NOW()
        FROM `tabCourse Schedule` cs
        JOIN `tabStudent Group` sg ON sg.name = cs.student_group
        JOIN `tabProgram` p        ON p.name = sg.program
        LEFT JOIN `tabStudent Attendance` sa
               ON sa.course_schedule = cs.name AND sa.docstatus = 1
        WHERE sg.academic_term = %(term)s
          AND cs.schedule_date <= CURDATE()
          {scope}
        GROUP BY p.department, sg.academic_year, cs.schedule_date
        """,
        {"term": term, "dates": tuple(dates) if dates else None},
    )


def _current_terms() -> list[str]:
    """Terms whose date range covers today — the only ones that change."""
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabAcademic Term`
        WHERE term_start_date <= CURDATE() AND term_end_date >= CURDATE()
        """,
        as_list=True,
    )
    if rows:
        return [r[0] for r in rows]
    # Between terms (vacation): fall back to the most recently ended term.
    rows = frappe.db.sql(
        """
        SELECT name FROM `tabAcademic Term`
        WHERE term_start_date <= CURDATE()
        ORDER BY term_end_date DESC LIMIT 1
        """,
        as_list=True,
    )
    return [r[0] for r in rows]


def _changed_scope(since, terms):
    """What the attendance changed since `since` touches in the summaries.

    Returns None when a full-term rebuild is the safer choice, else a dict:
      pairs  - (student, course): rows of rpt_student_course_term to redo
      slices - (student group, course): the classes those rows are summed from
      days   - (student group, date): rows of rpt_group_course_day to redo
      dates  - schedule dates of rpt_dept_term_day to redo
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT sa.student, cs.course, cs.student_group,
               sa.student_group, sa.date, cs.schedule_date
        FROM `tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
        WHERE sa.modified > %(since)s
        LIMIT %(limit)s
        """,
        {"since": since, "limit": MAX_CHANGED_ROWS + 1},
        as_list=True,
    )
    if len(rows) > MAX_CHANGED_ROWS:
        return None  # a backfill or bulk correction: rebuild the term

    pairs, slices, days, dates = set(), set(), set(), set()
    for student, course, cs_group, sa_group, att_date, schedule_date in rows:
        pairs.add((student, course))
        slices.add((cs_group, course))
        if sa_group and att_date:
            days.add((sa_group, att_date))
        if schedule_date:
            dates.add(schedule_date)

    # A student can attend one course through more than one group (shared
    # classes, sibling sections). The summary row lists every group it was
    # summed from, so add those groups' classes to the slices; otherwise the
    # recalculated row would lose the attendance from the other group.
    students = sorted({student for student, _ in pairs})
    for i in range(0, len(students), 1000):
        known = frappe.db.sql(
            f"""
            SELECT student, course, student_groups
            FROM {REPORTS_SCHEMA}.rpt_student_course_term
            WHERE academic_term IN %(terms)s AND student IN %(students)s
            """,
            {"terms": tuple(terms), "students": tuple(students[i : i + 1000])},
            as_list=True,
        )
        for student, course, groups in known:
            if (student, course) not in pairs or not groups:
                continue
            if len(groups) >= GROUPS_TEXT_LIMIT:
                return None  # the group list was cut off: cannot trust it
            slices.update((g, course) for g in groups.split(","))

    # Schedule edits and today's timetable move the "classes scheduled" count
    # even when no attendance changed.
    dates.update(
        r[0]
        for r in frappe.db.sql(
            """
            SELECT DISTINCT schedule_date FROM `tabCourse Schedule`
            WHERE modified > %(since)s AND schedule_date IS NOT NULL
            """,
            {"since": since},
            as_list=True,
        )
    )
    dates.add(frappe.utils.getdate())
    if len(dates) > MAX_CHANGED_DATES or len(days) > MAX_CHANGED_DAYS:
        return None
    return {"pairs": pairs, "slices": slices, "days": days, "dates": dates}


def _load_scope_tables(scope):
    """Put the scope in session-temporary tables the aggregations join to."""
    _drop_scope_tables()
    text = "varchar(140) NOT NULL"
    tables = (
        (TMP_PAIRS, f"student {text}, course {text}", "student, course", scope["pairs"]),
        (TMP_SLICES, f"student_group {text}, course {text}", "student_group, course", scope["slices"]),
        (TMP_DAYS, f"student_group {text}, att_date date NOT NULL", "student_group, att_date", scope["days"]),
    )
    # Create all three before filling any: Frappe refuses CREATE once the
    # transaction has written rows.
    for table, columns, key, _ in tables:
        # Same character set and collation as the tab* columns they join to,
        # so the joins can use the indexes on both sides.
        frappe.db.sql(
            f"""CREATE TEMPORARY TABLE {table} ({columns}, PRIMARY KEY ({key}))
                DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
        )
    for table, _, _, values in tables:
        values = sorted(values)
        for i in range(0, len(values), 500):
            chunk = values[i : i + 500]
            frappe.db.sql(
                f"INSERT INTO {table} VALUES " + ", ".join(["(%s, %s)"] * len(chunk)),
                tuple(v for row in chunk for v in row),
            )


def _drop_scope_tables():
    frappe.db.commit()  # Frappe refuses DROP/CREATE inside an open write transaction
    for table in (TMP_PAIRS, TMP_SLICES, TMP_DAYS):
        frappe.db.sql(f"DROP TEMPORARY TABLE IF EXISTS {table}")


def incremental_refresh():
    """About hourly: recalculate only the summary rows that changed.

    Reads the attendance rows modified since the last run (minus an overlap,
    so a save that committed late is not missed) and redoes just the summary
    rows those touch, each from all of its source rows. REPLACE INTO makes
    redoing a row harmless. Falls back to rebuilding the whole current term
    when the change is too large to be worth scoping, or on the first run.
    Hard deletes and renamed students/courses are handled by the nightly
    full rebuild, as before.
    """
    if not _refresh_allowed_now():
        return
    last_run = frappe.db.get_global(LAST_RUN_KEY)
    now = frappe.utils.now()
    terms = _current_terms()
    scope = None
    if last_run:
        since = frappe.utils.add_to_date(
            frappe.utils.get_datetime(last_run), minutes=-CHANGE_OVERLAP_MIN
        )
        scope = _changed_scope(since, terms)

    _non_locking_reads()
    try:
        if scope is None:
            for term in terms:
                # Commit after each statement: each REPLACE is idempotent, and a
                # short transaction keeps the rpt_* target locks + undo log small.
                _rebuild_term_student_course(term)
                frappe.db.commit()
                _rebuild_term_group_course_day(term)
                frappe.db.commit()
                _rebuild_term_dept_day(term)
                frappe.db.commit()
        else:
            if scope["pairs"]:
                _load_scope_tables(scope)
            for term in terms:
                if scope["pairs"]:
                    _rebuild_term_student_course(term, changed_only=True)
                    frappe.db.commit()
                    _rebuild_term_group_course_day(term, changed_only=True)
                    frappe.db.commit()
                _rebuild_term_dept_day(term, dates=scope["dates"])
                frappe.db.commit()
        frappe.db.set_global(LAST_RUN_KEY, now)
        frappe.db.commit()
    finally:
        _drop_scope_tables()
        _default_isolation()
    frappe.logger("srkr_reports_sync").info(
        "incremental refresh: "
        + (
            "full term rebuild"
            if scope is None
            else f"{len(scope['pairs'])} student-course rows, {len(scope['days'])} group-days, "
            f"{len(scope['dates'])} dates"
        )
        + f", terms={terms}"
    )


def nightly_full_rebuild():
    """~2 AM: rebuild every term with data + reconcile hard deletes.

    Hard deletes (46K schedules + 10K attendance rows deleted last year for
    holiday/cancellation cleanup) are invisible to modified-based increments.
    A full REPLACE-rebuild regenerates surviving aggregates, then we purge
    aggregate rows whose underlying (group, course, date) no longer has any
    submitted attendance — covering slices emptied by deletion.
    """
    terms = [r[0] for r in frappe.db.sql(ACTIVE_TERMS_SQL, as_list=True)]
    _non_locking_reads()
    try:
        _nightly_full_rebuild(terms)
    finally:
        _default_isolation()
    frappe.logger("srkr_reports_sync").info(
        f"nightly rebuild complete: terms={json.dumps(terms)}"
    )


def _nightly_full_rebuild(terms: list[str]):
    for term in terms:
        _rebuild_term_student_course(term)
        frappe.db.commit()
        _rebuild_term_group_course_day(term)
        frappe.db.commit()
        _rebuild_term_dept_day(term)
        frappe.db.commit()

    # Purge day-grain rows that no longer exist in the source.
    frappe.db.sql(
        f"""
        DELETE r FROM {REPORTS_SCHEMA}.rpt_group_course_day r
        LEFT JOIN (
            SELECT DISTINCT sa.student_group, cs.course, sa.date
            FROM `tabStudent Attendance` sa
            JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
            WHERE sa.docstatus = 1
        ) live ON live.student_group = r.student_group
              AND live.course = r.course AND live.date = r.schedule_date
        WHERE live.student_group IS NULL
        """
    )
    # Purge student×course aggregates for students with no remaining rows.
    frappe.db.sql(
        f"""
        DELETE r FROM {REPORTS_SCHEMA}.rpt_student_course_term r
        LEFT JOIN (
            SELECT DISTINCT sa.student, cs.course, sg.academic_term
            FROM `tabStudent Attendance` sa
            JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
            JOIN `tabStudent Group` sg ON sg.name = cs.student_group
            WHERE sa.docstatus = 1
        ) live ON live.student = r.student AND live.course = r.course
              AND live.academic_term = r.academic_term
        WHERE live.student IS NULL
        """
    )
    # Expensive data-quality metrics for the admin panel (full-table scans
    # belong here, not in a page load).
    frappe.db.sql(
        f"""
        REPLACE INTO {REPORTS_SCHEMA}.dq_metrics (metric, value, updated_at)
        SELECT 'cross_term_attendance_rows', COUNT(*), NOW()
        FROM `tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
        JOIN `tabStudent Group` sg_a ON sg_a.name = sa.student_group
        JOIN `tabStudent Group` sg_c ON sg_c.name = cs.student_group
        WHERE sa.docstatus = 1 AND sg_a.academic_term != sg_c.academic_term
        """
    )

    frappe.db.set_global(LAST_RUN_KEY, frappe.utils.now())
    frappe.db.commit()
