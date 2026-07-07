// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Full Term Daily Attendance by Course"] = {
    _allowed_groups: null,  // null = no restriction, [...] = allowed group names

    onload: function () {
        frappe.xcall(
            "srkr_frappe_app_api.srkr_frappe_app_api.report.full_term_daily_attendance_by_course.full_term_daily_attendance_by_course.get_instructor_allowed_groups_api"
        ).then(groups => {
            frappe.query_report.report_object._allowed_groups = groups;
        });
    },

    "filters": [
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group",
            "reqd": 1,
            "get_query": function () {
                let allowed = frappe.query_report.report_object._allowed_groups;
                if (!allowed) return {};  // no restriction
                if (!allowed.length) return { filters: { name: "__none__" } };
                return { filters: { name: ["in", allowed] } };
            },
            "on_change": function () {
                // When student group changes, update the course filter
                let student_group = frappe.query_report.get_filter_value("student_group");
                let course_filter = frappe.query_report.get_filter("course");

                // Clear the course filter first
                course_filter.df.options = [];
                course_filter.refresh();
                frappe.query_report.set_filter_value("course", "");

                if (student_group) {
                    // Call the Python API to get courses for the selected group
                    frappe.call({
                        method: "srkr_frappe_app_api.srkr_frappe_app_api.report.full_term_daily_attendance_by_course.full_term_daily_attendance_by_course.get_courses_for_student_group",
                        args: {
                            student_group: student_group
                        },
                        callback: function (r) {
                            if (r.message && r.message.length > 0) {
                                // Update the 'options' of the course filter
                                course_filter.df.options = r.message;
                                course_filter.refresh();
                            } else {
                                frappe.msgprint(__("No courses with scheduled classes found for the selected Student Group."));
                            }
                        }
                    });
                }
            }
        },
        {
            "fieldname": "course",
            "label": __("Course"),
            "fieldtype": "Select", // Use Select for dynamically loaded options
            "options": [], // Initially empty, will be populated by the on_change event
            "reqd": 1
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
    ]
};