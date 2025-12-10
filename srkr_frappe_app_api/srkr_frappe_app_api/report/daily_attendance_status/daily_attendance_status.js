// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Daily Attendance Status"] = {
    "filters": [
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            // "reqd": 1, // We've commented this out to allow Auto Email setup
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "program",
            "label": __("Program"),
            "fieldtype": "Link",
            "options": "Program"
        },
        {
            "fieldname": "instructor",
            "label": __("Instructor"),
            "fieldtype": "Link",
            "options": "Instructor"
        },
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group"
        },
        {
            "fieldname": "status",
            "label": __("Status"),
            "fieldtype": "Select",
            // Added "Partial" to the options
            "options": "All\nTaken\nPartial\nNot Taken"
        },
        {
            "fieldname": "gender",
            "label": __("Gender"),
            "fieldtype": "Link",
            "options": "Gender",
            "reqd": 0
        },
        {
            "fieldname": "hostel_opt_in",
            "label": __("Hostel Opt-in"),
            "fieldtype": "Select",
            "options": ["", "Yes", "No"],
            "reqd": 0
        }
    ],
    // NEW: Add a formatter for color-coding the status
    "formatter": function (value, row, column, data, default_formatter) {
        const formatted_value = default_formatter(value, row, column, data);

        if (column.fieldname === 'status') {
            if (value === "Not Taken") {
                return `<span style="color: red; font-weight: bold;">${formatted_value}</span>`;
            } else if (value === "Partial") {
                return `<span style="color: orange; font-weight: bold;">${formatted_value}</span>`;
            } else if (value === "Taken") {
                return `<span style="color: green; font-weight: bold;">${formatted_value}</span>`;
            }
        }

        return formatted_value;
    }
};