import calendar

import frappe
from frappe.utils import add_days, formatdate, getdate

from education.education.doctype.course_scheduling_tool.course_scheduling_tool import (
	CourseSchedulingTool,
)
from education.education.utils import OverlapError, get_overlap_for

SRKR_PERIODS = {
	"P1": ("09:00:00", "09:45:00"),
	"P2": ("09:45:00", "10:30:00"),
	"P3": ("10:30:00", "11:15:00"),
	"P4": ("11:15:00", "12:00:00"),
	"P5": ("13:30:00", "14:15:00"),
	"P6": ("14:15:00", "15:00:00"),
	"P7": ("15:00:00", "15:45:00"),
	"P8": ("15:45:00", "16:30:00"),
	"P9": ("16:30:00", "17:15:00"),
}
SRKR_PERIOD_KEYS = list(SRKR_PERIODS.keys())


class CustomCourseSchedulingTool(CourseSchedulingTool):
	@frappe.whitelist()
	def schedule_course(self, days):
		"""schedule_course, extended to skip holiday dates."""
		holiday_dates = self.get_holiday_dates()
		return self.schedule_course_with_holiday_skip(days, holiday_dates)

	def get_holiday_dates(self):
		holiday_list = frappe.get_all("Holiday List", fields=["name"], limit=1)
		if not holiday_list:
			return []

		holidays = frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list[0].name},
			fields=["holiday_date"],
		)
		return [h.holiday_date for h in holidays]

	def schedule_course_with_holiday_skip(self, days, holiday_dates):
		course_schedules = []
		course_schedules_errors = []
		rescheduled = []
		reschedule_errors = []
		skipped_holidays = []

		self.validate_mandatory(days)
		self.validate_date()
		self.instructor_name = frappe.db.get_value(
			"Instructor", self.instructor, "instructor_name"
		)

		group_based_on, course = frappe.db.get_value(
			"Student Group", self.student_group, ["group_based_on", "course"]
		)
		if group_based_on == "Course":
			self.course = course

		if self.reschedule:
			rescheduled, reschedule_errors = self.delete_course_schedule(
				rescheduled, reschedule_errors, days
			)

		holiday_dates = {getdate(d) for d in holiday_dates}
		date = self.course_start_date
		while date < self.course_end_date:
			if calendar.day_name[getdate(date).weekday()] in days:
				if getdate(date) in holiday_dates:
					skipped_holidays.append(formatdate(date))
				else:
					course_schedule = self.make_course_schedule(date)
					try:
						course_schedule.save()
					except OverlapError:
						course_schedules_errors.append(date)
					else:
						course_schedules.append(course_schedule)
			date = add_days(date, 1)

		return dict(
			course_schedules=course_schedules,
			course_schedules_errors=course_schedules_errors,
			rescheduled=rescheduled,
			reschedule_errors=reschedule_errors,
			skipped_holidays=skipped_holidays,
		)

	@frappe.whitelist()
	def schedule_period_block(self, days, start_period, block_size):
		"""
		Atomic period/block scheduling for the SRKR period picker.

		Checks every (period x date) slot in the block for a conflict
		(instructor, co-instructors, room, or student group already
		booked) using the same overlap check Course Schedule itself
		uses on save. If any slot conflicts, nothing is created and
		every conflict is reported. Otherwise all rows for the block
		are created in one go, skipping holiday dates the same way
		schedule_course does.
		"""
		block_size = int(block_size)
		start_idx = SRKR_PERIOD_KEYS.index(start_period)
		if start_idx + block_size > len(SRKR_PERIOD_KEYS):
			frappe.throw(frappe._("Block runs past the last period."))
		if start_idx < 4 and start_idx + block_size > 4:
			frappe.throw(frappe._("Block cannot span the lunch break (P4 -> P5)."))
		periods = SRKR_PERIOD_KEYS[start_idx : start_idx + block_size]

		self.validate_mandatory(days)
		self.validate_date()
		self.instructor_name = frappe.db.get_value(
			"Instructor", self.instructor, "instructor_name"
		)
		group_based_on, course = frappe.db.get_value(
			"Student Group", self.student_group, ["group_based_on", "course"]
		)
		if group_based_on == "Course":
			self.course = course

		holiday_dates = {getdate(d) for d in self.get_holiday_dates()}
		start_date = getdate(self.course_start_date)
		end_date = getdate(self.course_end_date)

		dates = []
		date = start_date
		while date < end_date:
			if calendar.day_name[date.weekday()] in days and date not in holiday_dates:
				dates.append(date)
			date = add_days(date, 1)

		# Phase 1: check every period x date slot for a conflict before creating anything.
		conflicts = []
		for period in periods:
			from_time, to_time = SRKR_PERIODS[period]
			for d in dates:
				probe = self.make_course_schedule(d)
				probe.from_time = from_time
				probe.to_time = to_time
				for fieldname in ("instructor", "co_instructor_1", "co_instructor_2", "room", "student_group"):
					value = probe.get(fieldname)
					if not value:
						continue
					existing = get_overlap_for(probe, "Course Schedule", fieldname, value)
					if existing:
						conflicts.append(
							{
								"period": period,
								"date": str(d),
								"field": fieldname,
								"value": value,
								"existing": existing.name,
							}
						)

		holidays_in_range = [formatdate(d) for d in holiday_dates if start_date <= d < end_date]

		if conflicts:
			return dict(created=False, conflicts=conflicts, skipped_holidays=holidays_in_range)

		# Phase 2: no conflicts anywhere in the block - create every row.
		created = []
		for period in periods:
			from_time, to_time = SRKR_PERIODS[period]
			for d in dates:
				course_schedule = self.make_course_schedule(d)
				course_schedule.from_time = from_time
				course_schedule.to_time = to_time
				course_schedule.save()
				created.append({"period": period, "date": str(d), "name": course_schedule.name})

		return dict(
			created=True,
			rows=created,
			skipped_holidays=holidays_in_range,
		)
