# Refresh jobs for the srkr_reports summary schema (read by the external
# srkr-academics-portal). Frappe/MariaDB stays the single source of truth —
# these jobs only aggregate FROM tab* INTO srkr_reports.rpt_*.
#
# Registered in hooks.py scheduler_events:
#   - incremental_refresh: cron every 20 min
#   - nightly_full_rebuild: cron 2 AM (also reconciles hard deletes via
#     tabDeleted Document — incremental-on-modified cannot see deletes)
#
# The denominator rules (docstatus=1, schedule_date <= today, sibling groups,
# per-term first-year floor from srkr_reports.cfg_term_settings) live in the
# aggregation SQL below and NOWHERE else. Change them only with Dean sign-off.

import json

import frappe

REPORTS_SCHEMA = "srkr_reports"
LAST_RUN_KEY = "srkr_reports_sync_last_run"

# Terms are auto-discovered: any academic term that has submitted attendance.
ACTIVE_TERMS_SQL = """
    SELECT DISTINCT sg.academic_term
    FROM `tabStudent Group` sg
    JOIN `tabStudent Attendance` sa
      ON sa.student_group = sg.name AND sa.docstatus = 1
    WHERE sg.academic_term IS NOT NULL
"""


def _rebuild_term_student_course(term: str):
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
        FROM `tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON cs.name = sa.course_schedule
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


def _rebuild_term_group_course_day(term: str):
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
        WHERE sa.docstatus = 1
          AND sg.academic_term = %(term)s
        GROUP BY sg.academic_year, p.department, sg.program,
                 sa.student_group, cs.course, c.course_name, sa.date
        """,
        {"term": term},
    )


def _rebuild_term_dept_day(term: str):
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
        GROUP BY p.department, sg.academic_year, cs.schedule_date
        """,
        {"term": term},
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


def incremental_refresh():
    """Every ~20 min: re-aggregate slices touched since the last run.

    Strategy: find (student_group, course) pairs and terms with attendance
    modified since last_run, then rebuild only the affected terms' slices.
    Because REPLACE INTO is idempotent at the aggregate grain, we simply
    rebuild the current term(s) — cheap (one term ≈ seconds) and immune to
    partial-slice bugs. Deletes are handled nightly.
    """
    last_run = frappe.db.get_global(LAST_RUN_KEY)
    changed = frappe.db.sql(
        """
        SELECT COUNT(*) FROM `tabStudent Attendance`
        WHERE modified > COALESCE(%(last_run)s, '1900-01-01')
        """,
        {"last_run": last_run},
        as_list=True,
    )[0][0]
    if not changed:
        return

    now = frappe.utils.now()
    for term in _current_terms():
        _rebuild_term_student_course(term)
        _rebuild_term_group_course_day(term)
        _rebuild_term_dept_day(term)
    frappe.db.set_global(LAST_RUN_KEY, now)
    frappe.db.commit()
    frappe.logger("srkr_reports_sync").info(
        f"incremental refresh: {changed} changed rows, terms={_current_terms()}"
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
    for term in terms:
        _rebuild_term_student_course(term)
        _rebuild_term_group_course_day(term)
        _rebuild_term_dept_day(term)

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
    frappe.logger("srkr_reports_sync").info(
        f"nightly rebuild complete: terms={json.dumps(terms)}"
    )
