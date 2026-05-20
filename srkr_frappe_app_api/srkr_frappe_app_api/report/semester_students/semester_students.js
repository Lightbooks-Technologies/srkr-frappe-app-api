// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Semester Students"] = {
	"filters": [
		{
			"fieldname": "semester",
			"label": __("Semester"),
			"fieldtype": "Link",
			"options": "Semester",
			"reqd": 1
		},
		{
			"fieldname": "program",
			"label": __("Program"),
			"fieldtype": "Link",
			"options": "Program"
		}
	]
};
