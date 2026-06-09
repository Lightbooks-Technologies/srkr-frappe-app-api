// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["EPF Monthly Report"] = {
	"filters": [
		{
			"fieldname": "month",
			"label": __("Month"),
			"fieldtype": "Select",
			"options": [
				"January",
				"February",
				"March",
				"April",
				"May",
				"June",
				"July",
				"August",
				"September",
				"October",
				"November",
				"December"
			],
			"reqd": 1,
			"default": frappe.datetime.str_to_obj(frappe.datetime.get_today())
				.toLocaleString("default", { month: "long" })
		},
		{
			"fieldname": "year",
			"label": __("Year"),
			"fieldtype": "Int",
			"reqd": 1,
			"default": frappe.datetime.str_to_obj(frappe.datetime.get_today()).getFullYear()
		}
	]
};
