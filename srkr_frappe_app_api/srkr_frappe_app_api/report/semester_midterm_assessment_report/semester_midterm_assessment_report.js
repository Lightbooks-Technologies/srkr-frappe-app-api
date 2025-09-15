// Copyright (c) 2024, your_name and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Semester Midterm Assessment Report"] = {
    "filters": [
        {
            "fieldname": "assessment",
            "label": __("Semester Midterm Assessment"),
            "fieldtype": "Link",
            "options": "Semester Midterm Assessment",
            "reqd": 1,
            "description": "Select the assessment document to view the detailed marksheet."
        }
    ]
};