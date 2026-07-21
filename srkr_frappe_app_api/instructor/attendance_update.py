# Update-only attendance corrections for the Instructor App.
#
# Policy: an instructor can correct a class's attendance only on the day the
# class ran, until 5:00 PM site time (Asia/Kolkata). After the cutoff the
# records are frozen for the app; later corrections go through the desk
# (program coordinators keep their allow_on_submit access there).
#
# This module never inserts rows — first-time marking stays on
# mark_attendances(). Students without an existing record are reported back
# as skipped, not created. Corrections bump `modified`, so the srkr_reports
# incremental refresh picks them up (same mechanism as bulk_mark_class).

import json
from datetime import datetime, time

import frappe
from frappe import _
from frappe.utils import formatdate, getdate, now, now_datetime, today

UPDATE_CUTOFF = time(17, 0)  # 5:00 PM site time
VALID_STATUSES = ("Present", "Absent")


def _window_for(schedule_date):
	deadline = datetime.combine(getdate(schedule_date), UPDATE_CUTOFF)
	now_dt = now_datetime()
	can_update = getdate(schedule_date) == getdate(today()) and now_dt <= deadline
	return can_update, deadline, now_dt


@frappe.whitelist()
def get_attendance_update_window(course_schedule):
	"""Whether this class's attendance can still be corrected, per the server
	clock. The app renders its Update button from this — never from the
	device clock — and update_class_attendance() re-validates on submit."""
	schedule_date = frappe.db.get_value("Course Schedule", course_schedule, "schedule_date")
	if not schedule_date:
		frappe.throw(_("Course Schedule {0} not found").format(course_schedule))
	can_update, deadline, now_dt = _window_for(schedule_date)
	return {
		"can_update": bool(can_update),
		"deadline": str(deadline),
		"server_now": str(now_dt),
	}


def _instructors_for_user(user):
	"""Instructor records linked to the session user, via the same
	User→Employee resolution get_instructor_info() uses."""
	employees = set()
	direct = frappe.get_doc("User", user).get("employee")
	if direct:
		employees.add(direct)
	for field in ("user_id", "company_email", "personal_email"):
		employees.update(
			e.name for e in frappe.get_all("Employee", filters={field: user}, fields=["name"])
		)
	if not employees:
		return []
	return [
		i.name
		for i in frappe.get_all(
			"Instructor", filters={"employee": ["in", list(employees)]}, fields=["name"]
		)
	]


def _check_ownership(schedules_meta):
	"""Block instructors from correcting other instructors' classes. Users
	with no Instructor record (e.g. coordinators using the app) fall back to
	the standard write permission on Student Attendance."""
	user_instructors = set(_instructors_for_user(frappe.session.user))
	if not user_instructors:
		frappe.has_permission("Student Attendance", ptype="write", throw=True)
		return
	for cs, meta in schedules_meta.items():
		schedule_instructors = {
			meta.instructor,
			meta.co_instructor_1,
			meta.co_instructor_2,
		} - {None, ""}
		if not user_instructors & schedule_instructors:
			frappe.throw(
				_("You are not an instructor for {0} and cannot update its attendance.").format(cs)
			)


@frappe.whitelist()
def update_class_attendance(course_schedule, changes):
	"""Correct existing attendance for today's class, until 5:00 PM.

	:param course_schedule: schedule name, or JSON list for multi-period labs
	:param changes: JSON list of {"student": ..., "status": "Present"|"Absent"}
	Returns {"updated": n, "unchanged": n, "skipped": [students with no record]}.
	"""
	if isinstance(course_schedule, str):
		try:
			schedules = json.loads(course_schedule)
		except ValueError:
			schedules = [course_schedule]
	else:
		schedules = course_schedule
	if not isinstance(schedules, list):
		schedules = [schedules]
	schedules = [s for s in schedules if s]

	if isinstance(changes, str):
		changes = json.loads(changes)
	if not schedules or not changes:
		return {"updated": 0, "unchanged": 0, "skipped": []}

	for c in changes:
		if c.get("status") not in VALID_STATUSES:
			frappe.throw(_("Invalid status {0} for student {1}").format(c.get("status"), c.get("student")))

	schedules_meta = {}
	for cs in schedules:
		meta = frappe.db.get_value(
			"Course Schedule",
			cs,
			["schedule_date", "instructor", "co_instructor_1", "co_instructor_2"],
			as_dict=True,
		)
		if not meta:
			frappe.throw(_("Course Schedule {0} not found").format(cs))
		can_update, deadline, _now = _window_for(meta.schedule_date)
		if not can_update:
			frappe.throw(
				_(
					"Attendance for {0} can only be updated until 5:00 PM on the day of the class ({1})."
				).format(cs, formatdate(meta.schedule_date))
			)
		schedules_meta[cs] = meta

	_check_ownership(schedules_meta)

	result = _apply_changes(schedules, changes)
	frappe.db.commit()
	return result


def _apply_changes(schedules, changes):
	"""Write path, separated from validation so selftest() can exercise it.
	Updates only rows that already exist; skipped students are returned,
	never inserted."""
	updated = unchanged = 0
	skipped = set()
	ts = now()
	user = frappe.session.user

	for cs in schedules:
		existing = frappe.db.sql(
			"""SELECT name, student, status FROM `tabStudent Attendance`
			   WHERE course_schedule = %s AND docstatus != 2""",
			(cs,),
			as_dict=True,
		)
		by_student = {r.student: r for r in existing}

		to_set = {status: [] for status in VALID_STATUSES}
		changed_here = []
		for c in changes:
			prior = by_student.get(c["student"])
			if prior is None:
				skipped.add(c["student"])
			elif prior.status != c["status"]:
				to_set[c["status"]].append(prior.name)
				changed_here.append(f"{c['student']} {prior.status}→{c['status']}")
			else:
				unchanged += 1

		for status, names in to_set.items():
			if names:
				frappe.db.sql(
					"""UPDATE `tabStudent Attendance`
					   SET status = %s, modified = %s, modified_by = %s
					   WHERE name IN %s""",
					(status, ts, user, tuple(names)),
				)
				updated += len(names)

		if changed_here:
			# audit trail: track_changes is off on Student Attendance, so leave
			# one compact note per class on its Course Schedule
			summary = ", ".join(changed_here[:20])
			if len(changed_here) > 20:
				summary += f", … +{len(changed_here) - 20} more"
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Info",
					"reference_doctype": "Course Schedule",
					"reference_name": cs,
					"content": f"Attendance corrected by {user}: {summary}",
				}
			).insert(ignore_permissions=True)

	return {"updated": updated, "unchanged": unchanged, "skipped": sorted(skipped)}


def selftest(course_schedule: str):
	"""Prove the update write path against real data, then roll back.

	Run on DEV only:  bench --site <site> execute \
	  srkr_frappe_app_api.instructor.attendance_update.selftest \
	  --kwargs "{'course_schedule': '...'}"

	Flips the status of the first 5 existing records for the schedule via the
	same _apply_changes the endpoint uses, re-reads them to verify status and
	`modified` both changed, includes one unknown student to prove no insert
	happens, and rolls everything back.
	"""
	rows = frappe.db.sql(
		"""SELECT name, student, status, modified FROM `tabStudent Attendance`
		   WHERE course_schedule = %s AND docstatus != 2
		   ORDER BY name LIMIT 5""",
		(course_schedule,),
		as_dict=True,
	)
	if not rows:
		return "no attendance records for this schedule — mark attendance first"

	flip = {"Present": "Absent", "Absent": "Present"}
	changes = [{"student": r.student, "status": flip.get(r.status, "Present")} for r in rows]
	changes.append({"student": "EDU-STU-SELFTEST-DOES-NOT-EXIST", "status": "Present"})
	count_before = frappe.db.count("Student Attendance", {"course_schedule": course_schedule})

	frappe.db.savepoint("att_update_selftest")
	try:
		result = _apply_changes([course_schedule], changes)
		after = frappe.db.sql(
			"""SELECT name, status, modified FROM `tabStudent Attendance`
			   WHERE name IN %s""",
			(tuple(r.name for r in rows),),
			as_dict=True,
		)
		after_by_name = {r.name: r for r in after}
		problems = []
		for r in rows:
			got = after_by_name[r.name]
			want = flip.get(r.status, "Present")
			if got.status != want:
				problems.append(f"{r.name}: status {got.status}, wanted {want}")
			if got.modified == r.modified:
				problems.append(f"{r.name}: modified not bumped")
		count_after = frappe.db.count("Student Attendance", {"course_schedule": course_schedule})
		if count_after != count_before:
			problems.append(f"row count changed {count_before} -> {count_after} (insert leaked!)")
		if result["skipped"] != ["EDU-STU-SELFTEST-DOES-NOT-EXIST"]:
			problems.append(f"unexpected skipped list: {result['skipped']}")
	finally:
		frappe.db.rollback(save_point="att_update_selftest")

	return {
		"result": result,
		"verdict": problems or "PASS — statuses flipped, modified bumped, no rows created, unknown student skipped",
	}
