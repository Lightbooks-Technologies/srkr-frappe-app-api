// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Student Applicant Profile Completion"] = {
	"filters": [
        {
            "fieldname": "student_applicant",
            "label": __("Student Applicant"),
            "fieldtype": "Link",
            "options": "Student Applicant"
        }
	],
    "formatter": function(value, row, column, data, default_formatter) {
        const formatted_value = default_formatter(value, row, column, data);

        // Don't color the main link column
        if (column.fieldname === 'applicant_name') {
            return formatted_value;
        }

        // For all other columns, apply color logic
        if (value === "Not Filled") {
            // If the cell says "Not Filled", make it red
            return `<span style="color: red;">${formatted_value}</span>`;
        } else if (value) {
            // For ANY other non-empty value ("Filled" or an actual value like a name/number), make it green
            return `<span style="color: green; font-weight: bold;">${formatted_value}</span>`;
        }
        
        // Return the default for any other case (e.g., empty cells)
        return formatted_value;
    }
};