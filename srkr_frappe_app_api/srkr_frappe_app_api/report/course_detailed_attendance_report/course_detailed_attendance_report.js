// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Course Detailed Attendance Report"] = {
    "filters": [
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group",
            "reqd": 1
        },
        {
            "fieldname": "course",
            "label": __("Course"),
            "fieldtype": "Link",
            "options": "Course",
            "reqd": 1
        }
    ],
    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (value === "A") {
            value = `<span style="color:red; font-weight:bold">${value}</span>`;
        }
        if (typeof value === "number" && column.fieldname.startsWith("sch_")) {
            value = `<span style="color:green">${value}</span>`;
        }
        return value;
    }
};
