// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Full Term Daily Attendance by Course"] = {
	"filters": [
        {
            "fieldname": "student_group",
            "label": __("Student Group"),
            "fieldtype": "Link",
            "options": "Student Group",
            "reqd": 1,
            "on_change": function() {
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
                        callback: function(r) {
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
        }
	]
};