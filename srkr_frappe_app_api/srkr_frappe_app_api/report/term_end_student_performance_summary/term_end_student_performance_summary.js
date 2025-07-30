// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Term-End Student Performance Summary"] = {
	"filters": [
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group",
            "reqd": 1 // This makes the filter mandatory
        }
	]
};