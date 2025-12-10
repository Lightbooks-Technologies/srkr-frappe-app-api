// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Student Cumulative Attendance"] = {
    "filters": [
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group",
            "reqd": 1,
            "default": "",
            "get_query": function () {
                return {
                    "filters": {
                        "disabled": 0
                    }
                };
            }
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

    "onload": function (report) {
        // Set default student group on initial load
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Student Group",
                filters: {
                    "disabled": 0
                },
                fields: ["name"],
                limit: 1,
                order_by: "creation desc"
            },
            callback: function (r) {
                if (r.message && r.message.length > 0) {
                    frappe.query_report.set_filter_value("student_group", r.message[0].name);
                }
            }
        });
    },

    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        // Color code attendance percentage
        if (column.fieldname == "attendance_percentage" && data) {
            let percentage = data.attendance_percentage;

            if (percentage >= 75) {
                // Green for good attendance (75% and above)
                value = `<span style="color: green; font-weight: bold;">${value}</span>`;
            } else if (percentage >= 50) {
                // Orange for moderate attendance (50-74%)
                value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
            } else {
                // Red for low attendance (below 50%)
                value = `<span style="color: red; font-weight: bold;">${value}</span>`;
            }
        }

        return value;
    }
};