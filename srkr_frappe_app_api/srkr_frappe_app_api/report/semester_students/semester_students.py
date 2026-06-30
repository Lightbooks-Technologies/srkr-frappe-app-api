# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def validate_filters(filters):
	if not filters.get("semester"):
		frappe.throw(_("Semester is required"))


def get_columns():
	return [
		{
			"fieldname": "student_name",
			"label": _("Name of Student"),
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"fieldname": "student_phone_number",
			"label": _("Student Phone Number"),
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"fieldname": "father_phone_number",
			"label": _("Father Phone Number"),
			"fieldtype": "Data",
			"width": 170,
		},
		{
			"fieldname": "student_id",
			"label": _("Student Id"),
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"fieldname": "gender",
			"label": _("Gender"),
			"fieldtype": "Link",
			"options": "Gender",
			"width": 100,
		},
		{
			"fieldname": "current_semester",
			"label": _("Current Semester"),
			"fieldtype": "Link",
			"options": "Semester",
			"width": 140,
		},
		{
			"fieldname": "program",
			"label": _("Program Name"),
			"fieldtype": "Link",
			"options": "Program",
			"width": 220,
		},
	]


def get_data(filters):
	conditions = ["pe.current_semester = %(semester)s", "pe.docstatus = 1"]

	if filters.get("program"):
		conditions.append("pe.program = %(program)s")

	return frappe.db.sql(
		f"""
		SELECT
			s.student_name,
			s.student_mobile_number AS student_phone_number,
			s.custom_father_mobile_number AS father_phone_number,
			s.custom_student_id AS student_id,
			s.gender,
			pe.current_semester,
			pe.program
		FROM `tabProgram Enrollment` pe
		INNER JOIN `tabStudent` s
			ON s.name = pe.student
		WHERE {" AND ".join(conditions)}
		ORDER BY
			s.custom_student_id,
			s.student_name
		""",
		filters,
		as_dict=True,
	)
