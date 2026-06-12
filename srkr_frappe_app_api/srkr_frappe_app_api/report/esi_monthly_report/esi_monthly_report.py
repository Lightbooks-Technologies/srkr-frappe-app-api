# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import calendar
import math

import frappe
from frappe import _
from frappe.utils import getdate


MONTH_MAP = {
	"January": 1,
	"February": 2,
	"March": 3,
	"April": 4,
	"May": 5,
	"June": 6,
	"July": 7,
	"August": 8,
	"September": 9,
	"October": 10,
	"November": 11,
	"December": 12,
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def validate_filters(filters):
	if not filters.get("month"):
		frappe.throw(_("Month is required"))

	if filters.get("month") not in MONTH_MAP:
		frappe.throw(_("Invalid month"))

	if not filters.get("year"):
		frappe.throw(_("Year is required"))

	try:
		int(filters.get("year"))
	except (TypeError, ValueError):
		frappe.throw(_("Year must be a valid number"))


def get_columns():
	return [
		{"label": _("SNO"),   "fieldname": "sno",      "fieldtype": "Int",      "width": 60},
		{"label": _("ESI ID"), "fieldname": "esi_id",  "fieldtype": "Data",     "width": 150},
		{"label": _("Name"),  "fieldname": "emp_name",  "fieldtype": "Data",     "width": 220},
		{"label": _("Desig"), "fieldname": "desig",     "fieldtype": "Data",     "width": 150},
		{"label": _("Wages"), "fieldname": "wages",     "fieldtype": "Currency", "width": 120},
		{"label": _("ESI"),   "fieldname": "esi",       "fieldtype": "Currency", "width": 100},
	]


def get_date_range(filters):
	month_num = MONTH_MAP[filters.get("month")]
	year = int(filters.get("year"))
	last_day = calendar.monthrange(year, month_num)[1]

	return getdate(f"{year}-{month_num:02d}-01"), getdate(f"{year}-{month_num:02d}-{last_day}")


def get_data(filters):
	start_date, end_date = get_date_range(filters)

	rows = frappe.db.sql(
		"""
		SELECT
			ss.employee,
			ss.employee_name,
			ss.gross_pay,
			e.custom_employee_esi_number,
			e.designation
		FROM `tabSalary Slip` ss
		JOIN `tabEmployee` e
			ON e.name = ss.employee
		WHERE ss.start_date >= %(start_date)s
			AND ss.end_date   <= %(end_date)s
			AND ss.docstatus   IN (0, 1)
			AND e.esi_eligible  = 1
		ORDER BY
			ss.gross_pay ASC,
			ss.employee_name ASC
		""",
		{"start_date": start_date, "end_date": end_date},
		as_dict=True,
	)

	data = []
	for index, row in enumerate(rows, start=1):
		gross = row.gross_pay or 0
		esi_wages = min(gross, 21000)
		esi = math.ceil(esi_wages * 0.0075)

		data.append(
			{
				"sno":      index,
				"esi_id":   row.custom_employee_esi_number or "",
				"emp_name": row.employee_name,
				"desig":    row.designation or "",
				"wages":    esi_wages,
				"esi":      esi,
			}
		)

	return data
