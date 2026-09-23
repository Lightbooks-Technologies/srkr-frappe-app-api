"""DeployU Connector — nightly one-way sync: ERP -> DeployU LMS.

Pushes academic structure (years/terms/programs/batches/sections/schedule),
roster (+ promotions), university results and per-course attendance to
the DeployU ingest APIs. ERP is source of truth; DeployU mirrors, never writes back.

Configuration (site_config.json):
    "deployu_api_url":       "https://srkr.deployu.ai",
    "deployu_college_slug":  "srkr",
    "deployu_erp_api_key":   "<colleges.erp_api_key>",
    "deployu_sync_enabled":  1,
    "deployu_sync_dry_run":  0,          # 1 = log payload counts, POST nothing
    "deployu_sync_programs": []          # optional list of program names to scope

Scheduling (hooks.py):
    "cron": { "0 3 * * *": ["srkr_frappe_app_api.deployu_connector.tasks.nightly_sync"] }
    (03:00 IST — after the 02:00 srkr_reports full rebuild, so summaries are fresh.)
    "cron": { "15 * * * *": ["...tasks.hourly_roster_sync"] }  — hourly roster delta.
    doc_events on Student / Program Enrollment / Student Group → enqueue_roster_delta:
    an enrolment, email change, roll-number change or section move reaches
    DeployU within seconds of being saved, not at 03:00.

Identity: every roster row carries erp_student_id (= Student.name), which
DeployU keys on — the roll number (temporary → permanent) and the email
(personal Gmail → college address) can both change without losing the account.
After the weekly FULL roster run, DeployU is asked to reconcile: active
students it did not see in that run are marked dropped.

Cron scheduler events run on the default RQ queue (300s timeout), which the
sync cannot fit in: nightly_sync only enqueues run_nightly_sync on the long
queue with its own timeout. Run by hand with:
    bench --site <site> execute srkr_frappe_app_api.deployu_connector.tasks.run_nightly_sync

Watermarks are stored via frappe defaults (frappe.db get/set_global), so each run
sends only rows changed since the last successful run. Re-sends are safe — every
DeployU endpoint is an idempotent upsert. To re-send the whole academic
structure (e.g. after DeployU starts accepting rows it used to skip):
    bench --site <site> execute srkr_frappe_app_api.deployu_connector.tasks.sync_structure --kwargs '{"full": true}'
"""
import json
import time
from datetime import datetime, timezone

import frappe
import requests

BATCH = 500
# The roster endpoint does several Supabase round trips per student (auth user,
# users row, profile upsert), ~0.5s each — 500 students cannot finish inside
# one HTTP request, so the roster goes in small chunks.
STUDENT_BATCH = 50
TIMEOUT = 120
# Attempts per POST; waits between them. Every endpoint is an idempotent upsert,
# so re-sending a chunk whose response was lost is safe.
RETRY_WAITS = (5, 20)
JOB_TIMEOUT = 3 * 60 * 60
SYNC_LOCK = "deployu_nightly_sync"
# Roster is sent as a delta; this weekday (Mon=0 .. Sun=6) re-sends everyone to
# catch bulk SQL updates that do not touch `modified`.
FULL_ROSTER_WEEKDAY = 6


# --------------------------------------------------------------------------
# config / plumbing
# --------------------------------------------------------------------------

def _cfg():
    conf = frappe.conf
    return {
        "url": (conf.get("deployu_api_url") or "").rstrip("/"),
        "slug": conf.get("deployu_college_slug"),
        "key": conf.get("deployu_erp_api_key"),
        "enabled": bool(conf.get("deployu_sync_enabled")),
        "dry_run": bool(conf.get("deployu_sync_dry_run")),
        "programs": conf.get("deployu_sync_programs") or [],
    }


def _post(cfg, path, payload):
    if cfg["dry_run"]:
        frappe.logger("deployu").info(f"[DRY RUN] POST {path}: {len(list(payload.values())[1])} rows")
        return {"dry_run": True}
    for wait in RETRY_WAITS + (None,):
        try:
            resp = requests.post(
                f"{cfg['url']}{path}",
                json=payload,
                headers={"x-api-key": cfg["key"], "Content-Type": "application/json"},
                timeout=TIMEOUT,
            )
            # 4xx is our payload or key — retrying cannot fix it.
            if resp.status_code < 500:
                resp.raise_for_status()
                return resp.json()
            error = requests.HTTPError(f"{resp.status_code} from {path}", response=resp)
        except (requests.ConnectionError, requests.Timeout) as e:
            error = e
        if wait is None:
            raise error
        frappe.logger("deployu").warning(f"POST {path} failed ({error}); retrying in {wait}s")
        time.sleep(wait)


def _chunks(rows, size=BATCH):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _get_watermark(name):
    return frappe.db.get_global(f"deployu_wm_{name}") or "2000-01-01 00:00:00"


def _set_watermark(name, value):
    frappe.db.set_global(f"deployu_wm_{name}", value)
    frappe.db.commit()


def _advance_watermark(name, value):
    """Move a watermark forward only — a full re-send must not rewind it."""
    if value and value > _get_watermark(name):
        _set_watermark(name, value)


def _safe_watermark(changed, sent_count):
    """Watermark after the first `sent_count` rows of an ascending `changed`
    list. Many students share one timestamp (a Student Group save stamps the
    whole section) and the delta query is `> watermark`, so the watermark may
    only reach a timestamp once every row carrying it has been sent."""
    if sent_count >= len(changed):
        return changed[-1] if changed else None
    unsent = changed[sent_count]
    done = [c for c in changed[:sent_count] if c < unsent]
    return done[-1] if done else None


def _program_filter(cfg, column):
    if not cfg["programs"]:
        return "", []
    ph = ", ".join(["%s"] * len(cfg["programs"]))
    return f" AND {column} IN ({ph})", list(cfg["programs"])


def _log_run(kind, sent, response, errors):
    frappe.logger("deployu").info(
        json.dumps({"job": kind, "sent": sent, "response": response, "errors": errors[:10]})
    )


# --------------------------------------------------------------------------
# 0. structure (academic years/terms, programs, batches, sections, schedule)
# --------------------------------------------------------------------------
# Mirrors the college's academic skeleton so nothing structural is hand-loaded:
# new AY/term -> semesters appear; new intake batch -> batch + mapping appear;
# new section -> group + mapping appear; new course schedule -> subject +
# instructor account + teaching assignment appear. Everything is an idempotent
# upsert on the DeployU side; kinds with a stable `modified` are watermarked,
# small dimension tables (years/terms/programs) are sent in full each night.

def _post_kind(cfg, kind, rows, errors, unresolved=None):
    resp = {}
    for chunk in _chunks(rows):
        resp = _post(cfg, "/api/admin/college/sync-structure",
                     {"college_slug": cfg["slug"], "kind": kind, "rows": chunk})
        if isinstance(resp, dict):
            errors += resp.get("errors", [])
            if unresolved is not None:
                unresolved.update(resp.get("unresolved_groups") or [])
    return resp


def sync_structure(cfg=None, full=False):
    """Push the academic skeleton. Delta by default (per-kind watermarks);
    full=True re-sends every batch, section and schedule tuple — used after a
    DeployU-side change in what it accepts, since the watermarks have already
    moved past the rows it previously skipped."""
    cfg = cfg or _cfg()
    errors = []
    sent = {}
    epoch = "2000-01-01 00:00:00"

    # -- academic years + terms (tiny; full send, order matters: years first) --
    ays = frappe.db.sql(
        """SELECT name, year_start_date AS start_date, year_end_date AS end_date
           FROM `tabAcademic Year` ORDER BY year_start_date""",
        as_dict=True,
    )
    for r in ays:
        r["start_date"], r["end_date"] = str(r["start_date"] or ""), str(r["end_date"] or "")
    if ays:
        _post_kind(cfg, "academic_years", ays, errors)
    sent["academic_years"] = len(ays)

    # -- programs (full send) --
    pf, pv = _program_filter(cfg, "program_name")
    programs = frappe.db.sql(
        f"""SELECT program_name AS name, program_abbreviation AS code
            FROM `tabProgram` WHERE COALESCE(program_abbreviation,'') != ''{pf}""",
        pv,
        as_dict=True,
    )
    if programs:
        _post_kind(cfg, "programs", programs, errors)
    sent["programs"] = len(programs)

    # -- terms AFTER programs (semester generation needs programs in place) --
    terms = frappe.db.sql(
        """SELECT name, academic_year, term_start_date AS start_date, term_end_date AS end_date
           FROM `tabAcademic Term` ORDER BY term_start_date""",
        as_dict=True,
    )
    for r in terms:
        r["start_date"], r["end_date"] = str(r["start_date"] or ""), str(r["end_date"] or "")
    if terms:
        _post_kind(cfg, "academic_terms", terms, errors)
    sent["academic_terms"] = len(terms)

    # -- batches: DISTINCT intake cohorts from the group `batch` field
    #    (e.g. BTECH-CSE-2023-2027) — SRKR names its Batch-type Student Groups
    #    per section-term, so the group NAME is a section, not the cohort. --
    wm = epoch if full else _get_watermark("structure_batches")
    pf, pv = _program_filter(cfg, "sg.program")
    batches = frappe.db.sql(
        f"""SELECT sg.batch AS erp_name, sg.program AS program_name,
                   MAX(sg.academic_year) AS academic_year, MAX(sg.modified) AS modified
            FROM `tabStudent Group` sg
            WHERE COALESCE(sg.batch,'') != '' AND sg.modified > %s{pf}
            GROUP BY sg.batch, sg.program
            ORDER BY MAX(sg.modified)""",
        [wm] + pv,
        as_dict=True,
    )
    if batches:
        _post_kind(cfg, "batches", [
            {"erp_name": b.erp_name, "program_name": b.program_name, "academic_year": b.academic_year}
            for b in batches
        ], errors)
        if not cfg["dry_run"]:
            _advance_watermark("structure_batches", str(batches[-1].modified))
    sent["batches"] = len(batches)

    # -- sections (watermarked). Only canonical ...SEM-NN-X letter sections are
    #    sections on the DeployU side — students belong to those. Lab sub-batch
    #    groups (...SEM-NN-X-XN) are NOT sent here; their schedules are folded
    #    onto the parent section by the schedule stage below. Elective splits
    #    (...-OE2-..., ...-PE4-...) have no single parent and are reported by
    #    DeployU as unresolved_groups. --
    wm = epoch if full else _get_watermark("structure_sections")
    pf, pv = _program_filter(cfg, "sg.program")
    sections = frappe.db.sql(
        f"""SELECT sg.name AS erp_group_name, sg.program AS program_name,
                   sg.batch AS batch_name, sg.modified
            FROM `tabStudent Group` sg
            WHERE sg.name REGEXP 'SEM-[0-9]+-[A-Z]$' AND sg.modified > %s{pf}
            ORDER BY sg.modified""",
        [wm] + pv,
        as_dict=True,
    )
    if sections:
        _post_kind(cfg, "sections", [
            {"erp_group_name": s.erp_group_name, "program_name": s.program_name, "batch_name": s.batch_name}
            for s in sections
        ], errors)
        if not cfg["dry_run"]:
            _advance_watermark("structure_sections", str(sections[-1].modified))
    sent["sections"] = len(sections)

    # -- course schedule -> subjects + instructors + teaching assignments
    #    (watermarked on schedule modified; DISTINCT tuples per run). The
    #    student_group is sent as-is, sub-batches included: DeployU resolves a
    #    ...SEM-NN-X-XN group to its parent section and keeps the original
    #    group name on the assignment as erp_ref. --
    wm = epoch if full else _get_watermark("structure_schedule")
    pf, pv = _program_filter(cfg, "sg.program")
    tuples = frappe.db.sql(
        f"""SELECT DISTINCT cs.instructor AS instructor_name, cs.course,
                   cs.student_group, sg.program,
                   COALESCE(e.user_id, e.company_email) AS instructor_email
            FROM `tabCourse Schedule` cs
            JOIN `tabStudent Group` sg ON sg.name = cs.student_group
            LEFT JOIN `tabInstructor` i ON i.name = cs.instructor
            LEFT JOIN `tabEmployee` e ON e.name = i.employee
            WHERE cs.modified > %s{pf}""",
        [wm] + pv,
        as_dict=True,
    )
    max_wm = frappe.db.sql(
        "SELECT MAX(modified) FROM `tabCourse Schedule` WHERE modified > %s", (wm,)
    )[0][0]
    unresolved = set()
    if tuples:
        _post_kind(cfg, "schedule", [
            {"instructor_name": r.instructor_name, "instructor_email": r.instructor_email,
             "course": r.course, "student_group": r.student_group, "program": r.program,
             "erp_ref": r.student_group}
            for r in tuples
        ], errors, unresolved=unresolved)
        if not cfg["dry_run"] and max_wm:
            _advance_watermark("structure_schedule", str(max_wm))
    sent["schedule_tuples"] = len(tuples)

    # -- finalize: regenerate cohort->lab rows + collect the unmapped report --
    resp = _post(cfg, "/api/admin/college/sync-structure",
                 {"college_slug": cfg["slug"], "kind": "finalize", "rows": []}) if not cfg["dry_run"] else {"dry_run": True}
    if isinstance(resp, dict) and resp.get("unmapped_subjects"):
        frappe.logger("deployu").info(json.dumps({"unmapped_lab_subjects": resp["unmapped_subjects"]}))
    if unresolved:
        frappe.logger("deployu").info(json.dumps(
            {"unresolved_schedule_groups": sorted(unresolved)[:50], "count": len(unresolved)}))
        sent["unresolved_groups"] = len(unresolved)

    _log_run("structure", sent, resp, errors)
    return {"sent": sent, "errors": len(errors)}


# --------------------------------------------------------------------------
# 1. roster (students + section + current semester -> drives promotion/gating)
# --------------------------------------------------------------------------

def sync_students(cfg=None, full=False):
    """Push the roster. Delta by default: students whose Student, Program
    Enrollment or current Student Group changed since the last clean run.
    full=True re-sends everyone (first run, weekly safety net, manual repair)."""
    cfg = cfg or _cfg()
    wm = "2000-01-01 00:00:00" if full else _get_watermark("students")
    run_started = datetime.now(timezone.utc).isoformat()
    pf, pv = _program_filter(cfg, "pe.program")
    rows = frappe.db.sql(
        f"""
        SELECT s.name AS erp_id, s.student_name, s.custom_student_id AS roll_number,
               LOWER(TRIM(s.student_email_id)) AS email,
               pe.program, pe.current_semester,
               sg.batch AS erp_batch_name, sg.name AS erp_group_name,
               GREATEST(s.modified, pe.modified, COALESCE(sg.modified, s.modified)) AS changed_at
        FROM `tabStudent` s
        JOIN `tabProgram Enrollment` pe ON pe.student = s.name AND pe.docstatus < 2
        LEFT JOIN (
            SELECT sgs.student, sg2.batch, sg2.name, sg2.modified,
                   ROW_NUMBER() OVER (PARTITION BY sgs.student ORDER BY sg2.academic_year DESC) rn
            FROM `tabStudent Group` sg2
            JOIN `tabStudent Group Student` sgs ON sgs.parent = sg2.name
            WHERE sg2.group_based_on = 'Batch'
        ) sg ON sg.student = s.name AND sg.rn = 1
        WHERE s.enabled = 1 AND s.custom_student_id IS NOT NULL
          AND pe.current_semester LIKE 'SEM-%%'{pf}
          AND GREATEST(s.modified, pe.modified, COALESCE(sg.modified, s.modified)) > %s
        ORDER BY changed_at
        """,
        pv + [wm],
        as_dict=True,
    )
    if not rows:
        _log_run("students", 0, {"note": "no changes since watermark"}, [])
        return {"sent": 0}

    # ERP batch name -> LMS batch id is resolved on the DeployU side via
    # erp_batch_mappings; we send names. Section letter parsed from group name.
    students, changed = [], []  # changed[i] = changed_at of students[i]
    for r in rows:
        if not r.email or not r.roll_number:
            continue
        changed.append(str(r.changed_at))
        sem = int(r.current_semester.split("-")[1])
        section = None
        if r.erp_group_name and "-SEM-" in r.erp_group_name:
            tail = r.erp_group_name.rsplit("-", 1)[-1]
            section = tail if len(tail) == 1 and tail.isalpha() else None
        students.append({
            "email": r.email,
            "full_name": r.student_name,
            "roll_number": r.roll_number,
            "erp_student_id": r.erp_id,
            "erp_batch_name": r.erp_batch_name,
            "current_year": (sem + 1) // 2,
            "current_sem_number": sem,
            "section": section,
        })

    # One bad chunk must not cost the rest of the roster: log it and keep going.
    # The watermark moves forward chunk by chunk while every chunk so far has
    # succeeded, so a run that is killed part-way (first full send, worker
    # restart) resumes where it stopped instead of starting over every night.
    errors, chunk_failures, resp, sent = [], [], {}, 0
    for start in range(0, len(students), STUDENT_BATCH):
        chunk = students[start : start + STUDENT_BATCH]
        try:
            resp = _post(cfg, "/api/admin/college/sync-students",
                         {"college_slug": cfg["slug"], "students": chunk})
        except Exception as e:
            chunk_failures.append(f"chunk starting {chunk[0]['roll_number']}: {e}")
            continue
        sent += len(chunk)
        errors += (resp.get("errors") or []) if isinstance(resp, dict) else []
        if not chunk_failures and not cfg["dry_run"]:
            _advance_watermark("students", _safe_watermark(changed, start + len(chunk)))

    failed_chunks = len(chunk_failures)
    if failed_chunks:
        frappe.log_error(
            title=f"DeployU sync: {failed_chunks} roster chunk(s) failed",
            message="\n".join(chunk_failures),
        )

    # After a complete FULL run DeployU knows everyone the ERP still has:
    # students it did not see since run_started (disabled / removed in the
    # ERP) are marked dropped there. DeployU refuses (409) if that would be
    # more than a fifth of the college — a broken run, not a mass exodus.
    reconcile = None
    if full and sent and not failed_chunks and not cfg["dry_run"]:
        try:
            reconcile = _post(cfg, "/api/admin/college/sync-students",
                              {"college_slug": cfg["slug"], "reconcile": {"since": run_started}})
        except requests.HTTPError as e:
            body = getattr(e.response, "text", "")[:500]
            frappe.log_error(title="DeployU sync: roster reconcile refused",
                             message=f"{e}\n{body}")
            reconcile = {"error": str(e)}
    _log_run("students", sent, {"last_chunk": resp, "reconcile": reconcile}, errors)
    return {"sent": sent, "failed_chunks": failed_chunks, "errors": len(errors), "reconcile": reconcile}


def enqueue_roster_delta(doc=None, method=None):
    """doc_events hook (Student, Program Enrollment, Student Group) AND the
    hourly cron land here: queue ONE watermark-based roster delta after the
    transaction commits. job_id + deduplicate mean a burst of edits (a class
    being enrolled, a section being rebuilt) becomes a single job; an edit
    that arrives while a delta is already running is picked up by the next
    hourly run because the watermark only advances to what was sent."""
    cfg = _cfg()
    if not cfg["enabled"]:
        return
    frappe.enqueue(
        "srkr_frappe_app_api.deployu_connector.tasks.run_roster_delta",
        queue="long",
        timeout=JOB_TIMEOUT,
        job_id="deployu-roster-delta",
        deduplicate=True,
        enqueue_after_commit=True,
    )


def hourly_roster_sync():
    """Cron (hourly). Cheap when nothing changed: one watermark query."""
    enqueue_roster_delta()


def run_roster_delta():
    """Long-queue job: delta roster push. Skips (not fails) when the nightly
    run holds the lock — that run sends the same changes."""
    cfg = _cfg()
    if not cfg["enabled"]:
        return
    if not frappe.db.sql("SELECT GET_LOCK(%s, 0)", SYNC_LOCK)[0][0]:
        frappe.logger("deployu").info("roster delta skipped — nightly sync holds the lock")
        return
    try:
        return sync_students(cfg, full=False)
    finally:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", SYNC_LOCK)


# --------------------------------------------------------------------------
# 2. results (semester rollup + subject detail)
# --------------------------------------------------------------------------

def sync_results(cfg=None):
    cfg = cfg or _cfg()
    wm = _get_watermark("results")
    parents = frappe.db.sql(
        """
        SELECT esr.name, esr.student, esr.semester_number, esr.sgpa, esr.exam_status,
               esr.modified, s.custom_student_id AS roll_number
        FROM `tabExam Semester Result` esr
        JOIN `tabStudent` s ON s.name = esr.student
        WHERE esr.modified > %s AND s.custom_student_id IS NOT NULL
        ORDER BY esr.modified
        """,
        (wm,),
        as_dict=True,
    )
    if not parents:
        _log_run("results", 0, {"note": "no changes since watermark"}, [])
        return {"sent": 0}

    names = [p.name for p in parents]
    ph = ", ".join(["%s"] * len(names))
    subj = frappe.db.sql(
        f"""SELECT parent, subject_code, subject_name, credits, grade, result, exammy
            FROM `tabExam Subject Result` WHERE parent IN ({ph})""",
        names,
        as_dict=True,
    )
    by_parent = {}
    for srow in subj:
        by_parent.setdefault(srow.parent, []).append({
            "code": srow.subject_code, "name": srow.subject_name,
            "credits": float(srow.credits or 0), "grade": srow.grade,
            "result": srow.result, "exam_month_year": srow.exammy,
        })

    results = [{
        "roll_number": p.roll_number,
        "semester_number": int(p.semester_number),
        "sgpa": float(p.sgpa) if p.sgpa is not None else None,
        "exam_status": p.exam_status,
        "subjects": by_parent.get(p.name, []),
    } for p in parents]

    errors, resp = [], {}
    for chunk in _chunks(results):
        resp = _post(cfg, "/api/admin/college/sync-results",
                     {"college_slug": cfg["slug"], "results": chunk})
        errors += resp.get("errors", []) if isinstance(resp, dict) else []
    if not cfg["dry_run"]:
        _set_watermark("results", str(parents[-1].modified))
    _log_run("results", len(results), resp, errors)
    return {"sent": len(results), "errors": len(errors)}


# --------------------------------------------------------------------------
# 3. attendance (straight copy of rpt_student_course_term rows)
# --------------------------------------------------------------------------

def sync_attendance(cfg=None):
    cfg = cfg or _cfg()
    wm = _get_watermark("attendance")
    pf, pv = _program_filter(cfg, "r.program")
    rows = frappe.db.sql(
        f"""
        SELECT r.custom_student_id AS roll_number, r.academic_year, r.academic_term,
               r.program_semester, r.course, r.course_name,
               r.present_count, r.absent_count, r.classes_held, r.attendance_pct,
               r.last_refreshed
        FROM srkr_reports.rpt_student_course_term r
        WHERE r.last_refreshed > %s AND r.custom_student_id IS NOT NULL{pf}
        ORDER BY r.last_refreshed
        """,
        [wm] + pv,
        as_dict=True,
    )
    if not rows:
        _log_run("attendance", 0, {"note": "no changes since watermark"}, [])
        return {"sent": 0}

    attendance = []
    for r in rows:
        code = None
        if r.course and r.course.rstrip().endswith(")") and "(" in r.course:
            code = r.course.rstrip()[:-1].rsplit("(", 1)[-1].strip() or None
        sem = None
        if r.program_semester and r.program_semester.startswith("SEM-"):
            sem = int(r.program_semester.split("-")[1])
        attendance.append({
            "roll_number": r.roll_number,
            "academic_year": r.academic_year,
            "academic_term": r.academic_term,
            "semester_number": sem,
            "course_code": code,
            "course_name": (r.course_name or r.course or "?")[:200],
            "present": int(r.present_count or 0),
            "absent": int(r.absent_count or 0),
            "held": int(r.classes_held or 0),
            "pct": float(r.attendance_pct) if r.attendance_pct is not None else None,
            "last_refreshed": str(r.last_refreshed) if r.last_refreshed else None,
        })

    errors, resp = [], {}
    for chunk in _chunks(attendance):
        resp = _post(cfg, "/api/admin/college/sync-attendance",
                     {"college_slug": cfg["slug"], "attendance": chunk})
        errors += resp.get("errors", []) if isinstance(resp, dict) else []
    if not cfg["dry_run"]:
        _set_watermark("attendance", str(rows[-1].last_refreshed))
    _log_run("attendance", len(attendance), resp, errors)
    return {"sent": len(attendance), "errors": len(errors)}


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def nightly_sync():
    """Cron entry point. Cron events run on the default queue (300s), so this
    only hands the real work to the long queue with a timeout it can fit in."""
    cfg = _cfg()
    if not cfg["enabled"]:
        frappe.logger("deployu").info("deployu sync disabled (deployu_sync_enabled=0)")
        return
    if not (cfg["url"] and cfg["slug"] and cfg["key"]):
        frappe.logger("deployu").error("deployu sync misconfigured — missing url/slug/key")
        return
    frappe.enqueue(
        "srkr_frappe_app_api.deployu_connector.tasks.run_nightly_sync",
        queue="long",
        timeout=JOB_TIMEOUT,
        job_id=f"deployu-nightly-sync|{frappe.utils.today()}",
        deduplicate=True,
    )


def run_nightly_sync(full_roster=None):
    """Structure first, then roster (identity), then marks, then attendance.
    Each stage is isolated: a failure is logged and the next stage still runs."""
    cfg = _cfg()
    if not cfg["enabled"]:
        return
    # Connection-scoped lock: a manual run and the cron run must not overlap,
    # and a dead worker releases it with its connection.
    if not frappe.db.sql("SELECT GET_LOCK(%s, 0)", SYNC_LOCK)[0][0]:
        frappe.logger("deployu").info("deployu sync skipped — a previous run is still active")
        return
    try:
        if full_roster is None:
            full_roster = frappe.utils.getdate().weekday() == FULL_ROSTER_WEEKDAY
        summary = {}
        for name, fn in (("structure", sync_structure),
                         ("students", lambda c: sync_students(c, full=full_roster)),
                         ("results", sync_results),
                         ("attendance", sync_attendance)):
            try:
                summary[name] = fn(cfg)
            except Exception:
                # Keywords, not positions: a traceback in the 140-char title
                # field raises inside this handler and kills the whole job.
                frappe.log_error(title=f"DeployU sync failed: {name}",
                                 message=frappe.get_traceback())
                summary[name] = {"error": True}
        frappe.logger("deployu").info(json.dumps({"nightly_sync": summary}))
        return summary
    finally:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", SYNC_LOCK)
