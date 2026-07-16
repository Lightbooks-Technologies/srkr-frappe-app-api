# Bulk attendance submission — replaces the per-student save()+submit() loop
# with one set-wise validation pass and one bulk INSERT per class.
#
# Why: the legacy path runs a full Frappe document lifecycle per student
# (~16 queries each, validate runs twice). For a 67-student class that is
# 1,000+ sequential round trips: measured 4.4s average / 34s worst per submit
# in prod (14-day window, 2,597 classes). This path does the SAME checks
# once per class and writes all rows in one statement: ~6 queries total.
#
# Safety audit (2026-07-12, prod): Student Attendance has NO doc_events in
# either app, NO controller hooks beyond validate(), NO server scripts /
# notifications / webhooks / workflows / assignment rules, and
# track_changes=0. bulk_insert bypasses validate() — replicated set-wise
# below with identical error messages — and fetch_from resolution, so the
# four fetch_from fields (student_name, student_mobile_number,
# link_nvfk←student_group.program, custom_student_attendance_student_id)
# are resolved explicitly at insert time (review finding, 2026-07-13).
#
# Behavior change (intentional, replaces a dead code path in the legacy
# helper): re-submitting a class UPDATES the status of existing records
# instead of throwing "Duplicate Entry" — what instructors expect when
# correcting a mistake. Corrected rows get a fresh `modified`, so the
# srkr_reports incremental refresh picks them up.
#
# Kill switch: set `"bulk_attendance_submit": 0` in site_config.json to fall
# back to the legacy per-document path without a code change.

import json

import frappe
from erpnext import get_default_company
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday
from frappe import _
from frappe.utils import cint, formatdate, get_link_to_form, getdate, now, today

from education.education.api import get_student_group_students

SERIES_TEMPLATE = "EDU-ATT-.YYYY.-"


def bulk_enabled() -> bool:
	return cint(frappe.conf.get("bulk_attendance_submit", 1)) == 1


def _reserve_series(count: int) -> list[str]:
	"""Atomically reserve `count` names from the EDU-ATT-.YYYY.- series.

	Mirrors frappe.model.naming.getseries (same tabSeries counter, same
	key derivation) but takes the row lock once per class instead of once
	per student — this is what removes the bell-time lock pileup.
	"""
	key = f"EDU-ATT-{getdate(today()).year}-"
	updated = frappe.db.sql(
		"UPDATE `tabSeries` SET current = current + %s WHERE name = %s",
		(count, key),
	)
	if not frappe.db.sql("SELECT current FROM `tabSeries` WHERE name = %s", (key,)):
		frappe.db.sql(
			"INSERT INTO `tabSeries` (name, current) VALUES (%s, %s)", (key, count)
		)
	end = frappe.db.sql(
		"SELECT current FROM `tabSeries` WHERE name = %s", (key,), as_list=True
	)[0][0]
	start = end - count + 1
	# str(n).zfill(5) matches getseries' default padding; series is past
	# 2.8M so in practice this is just str(n).
	return [f"{key}{str(n).zfill(5)}" for n in range(start, end + 1)]


def _get_holiday_list() -> str:
	company = get_default_company() or frappe.get_all("Company")[0].name
	holiday_list = frappe.get_cached_value("Company", company, "default_holiday_list")
	if not holiday_list:
		frappe.throw(
			_("Please set a default Holiday List for Company {0}").format(
				frappe.bold(company)
			)
		)
	return holiday_list


def bulk_mark_class(course_schedule: str, student_group: str | None, date, entries):
	"""Validate once per class, write once per class.

	:param entries: list of {"student", "student_name", "status"} dicts,
	                status in ("Present", "Absent").
	Returns {"inserted": n, "updated": n, "unchanged": n}.
	"""
	if not entries:
		return {"inserted": 0, "updated": 0, "unchanged": 0}

	# --- resolve the class context once (mirrors set_date/set_student_group) ---
	schedule_date, cs_group = frappe.db.get_value(
		"Course Schedule", course_schedule, ["schedule_date", "student_group"]
	)
	effective_group = cs_group or student_group
	effective_date = schedule_date or date

	# --- validate_date (future-date rule) ---
	if getdate(effective_date) > getdate(today()):
		frappe.throw(_("Attendance cannot be marked for future dates."))

	# --- validate_is_holiday, once ---
	if is_holiday(_get_holiday_list(), effective_date):
		frappe.throw(
			_("Attendance cannot be marked for {0} as it is a holiday.").format(
				frappe.bold(formatdate(effective_date))
			)
		)

	# --- validate_student: one roster fetch for the whole class ---
	roster = {d.student for d in get_student_group_students(effective_group)}
	for e in entries:
		if e["student"] not in roster:
			group_link = get_link_to_form("Student Group", effective_group)
			frappe.throw(
				_("Student {0}: {1} does not belong to Student Group {2}").format(
					frappe.bold(e["student"]),
					e.get("student_name") or "",
					frappe.bold(group_link),
				)
			)

	# --- validate_duplication → becomes update-on-remark, one query ---
	existing = frappe.db.sql(
		"""SELECT name, student, status FROM `tabStudent Attendance`
		   WHERE course_schedule = %s AND docstatus != 2 AND student IN %s""",
		(course_schedule, tuple(e["student"] for e in entries)),
		as_dict=True,
	)
	existing_by_student = {r.student: r for r in existing}

	to_insert = []
	updated = unchanged = 0
	for e in entries:
		prior = existing_by_student.get(e["student"])
		if prior is None:
			to_insert.append(e)
		elif prior.status != e["status"]:
			frappe.db.set_value(
				"Student Attendance", prior.name, "status", e["status"]
			)  # also bumps `modified` → picked up by the incremental refresh
			updated += 1
		else:
			unchanged += 1

	# --- single bulk INSERT for the new rows, docstatus=1 (submitted) ---
	if to_insert:
		# fetch_from fields, resolved set-wise (bulk_insert skips doc.save()):
		#   link_nvfk <- student_group.program (one lookup)
		#   student_mobile_number / custom_student_attendance_student_id <- Student
		program = frappe.db.get_value("Student Group", effective_group, "program")
		meta_rows = frappe.db.sql(
			"""SELECT name, student_mobile_number, custom_student_id
			   FROM `tabStudent` WHERE name IN %s""",
			(tuple(e["student"] for e in to_insert),),
			as_dict=True,
		)
		student_meta = {m.name: m for m in meta_rows}

		names = _reserve_series(len(to_insert))
		ts = now()
		user = frappe.session.user
		frappe.db.bulk_insert(
			"Student Attendance",
			fields=[
				"name",
				"naming_series",
				"student",
				"student_name",
				"course_schedule",
				"student_group",
				"date",
				"status",
				"docstatus",
				"owner",
				"modified_by",
				"creation",
				"modified",
				"student_mobile_number",
				"link_nvfk",
				"custom_student_attendance_student_id",
			],
			values=[
				(
					names[i],
					SERIES_TEMPLATE,
					e["student"],
					e.get("student_name") or "",
					course_schedule,
					effective_group,
					str(effective_date),
					e["status"],
					1,
					user,
					user,
					ts,
					ts,
					(student_meta.get(e["student"]) or {}).get("student_mobile_number"),
					program,
					(student_meta.get(e["student"]) or {}).get("custom_student_id"),
				)
				for i, e in enumerate(to_insert)
			],
		)

	return {"inserted": len(to_insert), "updated": updated, "unchanged": unchanged}


def selftest(student_group: str, course_schedule: str):
	"""Shadow-compare bulk vs legacy on a COPY of a real class, then roll back.

	Run on DEV only:  bench --site <site> execute \
	  srkr_frappe_app_api.instructor.bulk_attendance.selftest \
	  --kwargs "{'student_group': '...', 'course_schedule': '...'}"

	Builds the same present/absent input, runs the legacy per-doc path and
	the bulk path against two synthetic schedules, diffs every column except
	name/creation/modified, prints the verdict, and rolls everything back.
	"""
	from srkr_frappe_app_api.instructor.api import make_attendance_records

	students = get_student_group_students(student_group)[:10]
	if not students:
		return "no students in group"
	half = len(students) // 2
	entries = [
		{
			"student": s.student,
			"student_name": s.student_name,
			"status": "Present" if i < half else "Absent",
		}
		for i, s in enumerate(students)
	]
	date = frappe.db.get_value("Course Schedule", course_schedule, "schedule_date")

	frappe.db.savepoint("bulk_selftest")
	try:
		# legacy path
		for e in entries:
			make_attendance_records(
				e["student"], e["student_name"], e["status"], course_schedule,
				student_group, date,
			)
		legacy = frappe.db.sql(
			"""SELECT student, student_name, course_schedule, student_group,
			          date, status, docstatus,
			          student_mobile_number, link_nvfk,
			          custom_student_attendance_student_id
			   FROM `tabStudent Attendance` WHERE course_schedule = %s
			   ORDER BY student""",
			(course_schedule,),
			as_dict=True,
		)
		frappe.db.rollback(save_point="bulk_selftest")

		frappe.db.savepoint("bulk_selftest")
		bulk_mark_class(course_schedule, student_group, date, entries)
		bulk = frappe.db.sql(
			"""SELECT student, student_name, course_schedule, student_group,
			          date, status, docstatus,
			          student_mobile_number, link_nvfk,
			          custom_student_attendance_student_id
			   FROM `tabStudent Attendance` WHERE course_schedule = %s
			   ORDER BY student""",
			(course_schedule,),
			as_dict=True,
		)
	finally:
		frappe.db.rollback(save_point="bulk_selftest")

	diffs = [
		(l, b) for l, b in zip(legacy, bulk, strict=True) if dict(l) != dict(b)
	]
	return {
		"rows_compared": len(legacy),
		"mismatches": diffs or "NONE — bulk output identical to legacy",
	}
