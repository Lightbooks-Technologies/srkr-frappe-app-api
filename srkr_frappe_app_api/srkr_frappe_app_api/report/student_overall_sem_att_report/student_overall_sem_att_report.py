# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate

def execute(filters=None):
    if not filters:
        return [], []

    custom_student_id = filters.get("custom_student_id")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")

    if not custom_student_id or not from_date or not to_date:
        return [], []

    # Get Student Name (ID) from Custom ID
    student = frappe.get_value("Student", {"custom_student_id": custom_student_id}, "name")
    if not student:
        frappe.msgprint(_("Student with ID {0} not found.").format(custom_student_id))
        return [], []

    # Get all attendance records for this student in the date range
    # This will give us the actual courses they attended
    attendance_records = frappe.db.sql("""
        SELECT DISTINCT 
            sa.date,
            sa.course_schedule,
            sa.status,
            cs.course,
            cs.from_time,
            c.course_name
        FROM `tabStudent Attendance` sa
        JOIN `tabCourse Schedule` cs ON sa.course_schedule = cs.name
        JOIN `tabCourse` c ON cs.course = c.name
        WHERE 
            sa.student = %(student)s
            AND sa.date BETWEEN %(from_date)s AND %(to_date)s
            AND sa.docstatus = 1
        ORDER BY sa.date, cs.from_time
    """, {
        "student": student,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=1)

    if not attendance_records:
        frappe.msgprint(_("No attendance records found for this student in the selected date range."))
        return [], []

    # Get unique courses from attendance records
    courses = {}
    for record in attendance_records:
        if record.course not in courses:
            courses[record.course] = record.course_name

    # Sort courses by name for consistent column order
    sorted_courses = [{"name": k, "course_name": v} for k, v in sorted(courses.items(), key=lambda x: x[1])]

    columns = get_columns(sorted_courses)
    data = get_data(attendance_records, sorted_courses)

    return columns, data

def get_columns(courses):
    columns = [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "day", "label": _("Day"), "fieldtype": "Data", "width": 100}
    ]

    for course in courses:
        columns.append({
            "fieldname": frappe.scrub(course["name"]),
            "label": course["course_name"],
            "fieldtype": "Data",
            "width": 120
        })

    return columns

def get_data(attendance_records, courses):
    # Group by Date
    data_map = {}
    
    for record in attendance_records:
        date_str = record.date.strftime("%Y-%m-%d")
        if date_str not in data_map:
            data_map[date_str] = {
                "date": record.date,
                "day": record.date.strftime("%A"),
            }
        
        course_field = frappe.scrub(record.course)
        status = record.status
        
        # Abbreviate status
        status_abbr = status
        if status == "Present": 
            status_abbr = "P"
        elif status == "Absent": 
            status_abbr = "A"
        elif status == "On Leave": 
            status_abbr = "L"
        elif status == "Cancelled": 
            status_abbr = "C"
        else:
            status_abbr = status[0].upper() if status else "?"

        # If multiple classes of same course on same day, concatenate
        if course_field in data_map[date_str]:
            data_map[date_str][course_field] += ", " + status_abbr
        else:
            data_map[date_str][course_field] = status_abbr

    # Flatten to list and sort by date
    data = []
    sorted_dates = sorted(data_map.keys())
    for date_key in sorted_dates:
        data.append(data_map[date_key])

    return data
