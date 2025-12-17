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
            cs.to_time,
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

    columns = get_columns(attendance_records)
    data = get_data(attendance_records, columns)

    return columns, data

def format_time_from_timedelta(time_delta):
    """Convert timedelta to formatted time string like '9:00 am'"""
    if not time_delta:
        return ""
    
    total_seconds = int(time_delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    from_dt = frappe.utils.datetime.datetime.strptime(f"{hours:02d}:{minutes:02d}", "%H:%M")
    return from_dt.strftime("%I:%M %p").lower().lstrip('0')

def get_columns(attendance_records):
    """
    Generate columns: Date, Day, and one column per unique class session (course + time slot)
    """
    columns = [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "day", "label": _("Day"), "fieldtype": "Data", "width": 100}
    ]

    # Get unique class sessions (course + time combination)
    class_sessions = {}
    
    for record in attendance_records:
        from_time_str = format_time_from_timedelta(record.from_time)
        to_time_str = format_time_from_timedelta(record.to_time)
        
        # Create a unique key for this class session
        session_key = f"{record.course}_{record.from_time}_{record.to_time}"
        
        if session_key not in class_sessions:
            # Create column label with course name and time
            if from_time_str and to_time_str:
                label = f"{record.course_name}\n({from_time_str} - {to_time_str})"
            else:
                label = record.course_name
            
            class_sessions[session_key] = {
                "course": record.course,
                "course_name": record.course_name,
                "from_time": record.from_time,
                "to_time": record.to_time,
                "label": label,
                "fieldname": frappe.scrub(session_key)
            }
    
    # Sort sessions by course name and time
    sorted_sessions = sorted(class_sessions.values(), 
                            key=lambda x: (x["course_name"], x["from_time"] or 0))
    
    for session in sorted_sessions:
        columns.append({
            "fieldname": session["fieldname"],
            "label": session["label"],
            "fieldtype": "Data",
            "width": 150
        })

    return columns

def get_data(attendance_records, columns):
    """
    Build data rows grouped by date
    """
    # Group by Date
    data_map = {}
    
    for record in attendance_records:
        date_str = record.date.strftime("%Y-%m-%d")
        if date_str not in data_map:
            data_map[date_str] = {
                "date": record.date,
                "day": record.date.strftime("%A"),
            }
        
        # Create session key matching the column fieldname
        session_key = f"{record.course}_{record.from_time}_{record.to_time}"
        session_fieldname = frappe.scrub(session_key)
        
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

        # Set the status in the appropriate column
        data_map[date_str][session_fieldname] = status_abbr

    # Flatten to list and sort by date
    data = []
    sorted_dates = sorted(data_map.keys())
    for date_key in sorted_dates:
        data.append(data_map[date_key])

    return data
