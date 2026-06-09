# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import calendar

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
		{"label": _("SNO"), "fieldname": "sno", "fieldtype": "Int", "width": 60},
		{"label": _("PF NO"), "fieldname": "pf_no", "fieldtype": "Data", "width": 140},
		{"label": _("NAME"), "fieldname": "name_", "fieldtype": "Data", "width": 200},
		{"label": _("GROSS WAGES"), "fieldname": "gross_wages", "fieldtype": "Currency", "width": 120},
		{"label": _("EPF WAGES"), "fieldname": "epf_wages", "fieldtype": "Currency", "width": 120},
		{"label": _("EPS WAGES"), "fieldname": "eps_wages", "fieldtype": "Currency", "width": 120},
		{"label": _("EDLI WAGES"), "fieldname": "edli_wages", "fieldtype": "Currency", "width": 120},
		{"label": _("EPF"), "fieldname": "epf", "fieldtype": "Currency", "width": 100},
		{"label": _("FPF"), "fieldname": "fpf", "fieldtype": "Currency", "width": 100},
		{"label": _("EPF1"), "fieldname": "epf1", "fieldtype": "Currency", "width": 100},
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
			ss.name AS salary_slip,
			ss.employee,
			ss.employee_name,
			e.provident_fund_account,
			e.date_of_birth,
			MAX(CASE WHEN ssd.abbr = 'BP' THEN ssd.amount ELSE 0 END) AS bp,
			MAX(CASE WHEN ssd.abbr IN ('DA', 'DAH', 'DAL', 'DAZ') THEN ssd.amount ELSE 0 END) AS da,
			MAX(CASE WHEN ssd.abbr = 'EPF' THEN ssd.amount ELSE 0 END) AS epf_amount
		FROM `tabSalary Slip` ss
		INNER JOIN `tabEmployee` e
			ON e.name = ss.employee
		INNER JOIN `tabSalary Detail` ssd
			ON ssd.parent = ss.name
			AND ssd.parenttype = 'Salary Slip'
		WHERE ss.start_date >= %(start_date)s
			AND ss.end_date <= %(end_date)s
			AND ss.docstatus IN (0, 1)
		GROUP BY
			ss.name,
			ss.employee,
			ss.employee_name,
			e.provident_fund_account,
			e.date_of_birth
		ORDER BY
			ss.employee,
			ss.employee_name,
			ss.name
		""",
		{"start_date": start_date, "end_date": end_date},
		as_dict=True,
	)

	data = []
	for index, row in enumerate(rows, start=1):
		bp = row.bp or 0
		da = row.da or 0
		epf_amount = row.epf_amount or 0

		gross_wages = min(bp + da, 15000)
		eps_eligible = not is_eps_exempt(row.date_of_birth, start_date)
		eps_wages = gross_wages if eps_eligible else 0
		fpf = min(round(eps_wages * 0.0833), 1250) if eps_eligible else 0

		data.append(
			{
				"sno": index,
				"pf_no": row.provident_fund_account or "",
				"name_": row.employee_name,
				"gross_wages": gross_wages,
				"epf_wages": gross_wages,
				"eps_wages": eps_wages,
				"edli_wages": gross_wages,
				"epf": epf_amount,
				"fpf": fpf,
				"epf1": epf_amount - fpf,
			}
		)

	return data


def is_eps_exempt(date_of_birth, payroll_month_start):
	if not date_of_birth:
		return False

	date_of_birth = getdate(date_of_birth)
	payroll_month_start = getdate(payroll_month_start)

	age = payroll_month_start.year - date_of_birth.year
	if (payroll_month_start.month, payroll_month_start.day) < (date_of_birth.month, date_of_birth.day):
		age -= 1

	return age >= 58
