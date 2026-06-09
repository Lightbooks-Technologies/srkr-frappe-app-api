# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _
from frappe.utils import flt, getdate


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
		{"label": _("SNO"), "fieldname": "sno", "fieldtype": "Int", "width": 60},
		{"label": _("NAME"), "fieldname": "name_", "fieldtype": "Data", "width": 220},
		{"label": _("DESIG"), "fieldname": "designation", "fieldtype": "Data", "width": 180},
		{"label": _("ACCOUNT NUMBER"), "fieldname": "account_number", "fieldtype": "Data", "width": 150},
		{"label": _("NETPAY"), "fieldname": "net_pay", "fieldtype": "Currency", "width": 120},
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
			ss.net_pay,
			e.designation,
			e.bank_ac_no
		FROM `tabSalary Slip` ss
		INNER JOIN `tabEmployee` e
			ON e.name = ss.employee
		WHERE ss.start_date >= %(start_date)s
			AND ss.end_date <= %(end_date)s
			AND ss.docstatus IN (0, 1)
		ORDER BY
			ss.employee,
			ss.employee_name,
			ss.name
		""",
		{"start_date": start_date, "end_date": end_date},
		as_dict=True,
	)

	data = []
	total_net_pay = 0

	for index, row in enumerate(rows, start=1):
		net_pay = flt(row.net_pay)
		total_net_pay += net_pay

		data.append(
			{
				"sno": index,
				"name_": row.employee_name,
				"designation": row.designation or "",
				"account_number": row.bank_ac_no or "",
				"net_pay": net_pay,
			}
		)

	if data:
		data.append(
			{
				"sno": None,
				"name_": _("TOTAL"),
				"designation": "",
				"account_number": "",
				"net_pay": total_net_pay,
			}
		)

	return data
