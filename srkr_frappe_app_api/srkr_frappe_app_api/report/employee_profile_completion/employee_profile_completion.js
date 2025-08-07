// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Profile Completion"] = {
	"filters": [
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        }
	],
    "formatter": function(value, row, column, data, default_formatter) {
        const formatted_value = default_formatter(value, row, column, data);

        // Color-code the completion percentage
        if (column.fieldname === 'completion_percentage') {
            if (value < 50) {
                return `<span style="color: red; font-weight: bold;">${formatted_value}</span>`;
            } else if (value < 100) {
                return `<span style="color: orange; font-weight: bold;">${formatted_value}</span>`;
            } else {
                return `<span style="color: green; font-weight: bold;">${formatted_value}</span>`;
            }
        }
        
        // Color-code the "Filled" / "Not Filled" status
        if (value === "Filled") {
            return `<span style="color: green;">${formatted_value}</span>`;
        } else if (value === "Not Filled") {
            return `<span style="color: red;">${formatted_value}</span>`;
        }
        
        // For all other cases, return the default formatted value
        return formatted_value;
    }
};