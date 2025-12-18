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

    # 1. Get Student Groups the student is part of (Formal Membership)
    formal_groups = frappe.get_all("Student Group Student", 
                                    filters={"student": student, "active": 1}, 
                                    fields=["parent"])
    
    # 1b. Get Student Groups from their Attendance records (Historical/Actual)
    attendance_groups = frappe.db.sql("""
        SELECT DISTINCT student_group 
        FROM `tabStudent Attendance` 
        WHERE student = %s AND docstatus = 1
    """, student)

    # Combine all group names
    group_names = set([g.parent for g in formal_groups])
    for g in attendance_groups:
        if g[0]: group_names.add(g[0])

    if not group_names:
        frappe.msgprint(_("Student is not assigned to any active Student Group and has no attendance history."))
        return [], []

    # 2. Get all Course Schedules for these groups
    # Note: Using COALESCE on student_group to handle potential nulls, though unlikely
    schedules = frappe.db.sql("""
        SELECT 
            cs.name, cs.schedule_date, cs.from_time, cs.to_time, cs.course, c.course_name
        FROM `tabCourse Schedule` cs
        JOIN `tabCourse` c ON cs.course = c.name
        WHERE 
            cs.student_group IN %(group_names)s
            AND cs.schedule_date BETWEEN %(from_date)s AND %(to_date)s
            AND cs.docstatus = 1
        ORDER BY cs.schedule_date, cs.from_time
    """, {
        "group_names": list(group_names),
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=1)

    if not schedules:
        # Fallback: Check if there are ANY attendance records in the range (even if not linked to these groups)
        # This covers cases where student attended a class not formally assigned to their group
        schedules = frappe.db.sql("""
            SELECT DISTINCT
                cs.name, cs.schedule_date, cs.from_time, cs.to_time, cs.course, c.course_name
            FROM `tabStudent Attendance` sa
            JOIN `tabCourse Schedule` cs ON sa.course_schedule = cs.name
            JOIN `tabCourse` c ON cs.course = c.name
            WHERE 
                sa.student = %(student)s
                AND sa.date BETWEEN %(from_date)s AND %(to_date)s
                AND sa.docstatus = 1
            ORDER BY cs.schedule_date, cs.from_time
        """, {
            "student": student,
            "from_date": from_date,
            "to_date": to_date
        }, as_dict=1)

    if not schedules:
        frappe.msgprint(_("No schedules or attendance records found for this student in the selected date range."))
        return [], []

    # 3. Get Attendance Records for the student
    attendance = frappe.get_all("Student Attendance",
        filters={
            "student": student,
            "date": ["between", [from_date, to_date]],
            "docstatus": 1
        },
        fields=["course_schedule", "status"]
    )
    attendance_map = {a.course_schedule: a.status for a in attendance}

    columns = get_columns(schedules)
    data = get_data(schedules, attendance_map, columns)

    return columns, data

def format_time_from_timedelta(time_delta):
    """Convert timedelta to formatted time string like '9:00 am'"""
    if not time_delta:
        return ""
    
    total_seconds = int(time_delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    # Use 00:00 as base date to handle time extraction
    from_dt = frappe.utils.datetime.datetime.strptime(f"{hours:02d}:{minutes:02d}", "%H:%M")
    return from_dt.strftime("%I:%M %p").lower().lstrip('0')

def get_columns(schedules):
    """
    Generate columns: Date, Day, and dynamic Period columns based on max classes in a day.
    """
    columns = [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "day", "label": _("Day"), "fieldtype": "Data", "width": 100}
    ]

    # Calculate max classes any day has to determine number of Period columns
    day_counts = {}
    for record in schedules:
        date_str = record.schedule_date.strftime("%Y-%m-%d")
        day_counts[date_str] = day_counts.get(date_str, 0) + 1
    
    max_periods = max(day_counts.values()) if day_counts else 0

    for i in range(1, max_periods + 1):
        columns.append({
            "fieldname": f"period_{i}",
            "label": _("Period {0}").format(i),
            "fieldtype": "Data",
            "width": 150
        })

    return columns

def get_data(schedules, attendance_map, columns):
    """
    Build data rows grouped by date, mapping scheduled classes chronologically to Period columns
    """
    # 1. Group schedules by date and sort them by time
    date_groups = {}
    for record in schedules:
        date_str = record.schedule_date.strftime("%Y-%m-%d")
        if date_str not in date_groups:
            date_groups[date_str] = []
        date_groups[date_str].append(record)
    
    # 2. Process each date group to build rows
    data = []
    sorted_dates = sorted(date_groups.keys())
    
    for date_key in sorted_dates:
        records = date_groups[date_key]
        # Sort chronologically by from_time
        records.sort(key=lambda x: x.from_time or 0)
        
        # Start building the row
        row = {
            "date": records[0].schedule_date,
            "day": records[0].schedule_date.strftime("%A"),
        }
        
        # 3. Fill Period columns (1st record -> Period 1, 2nd -> Period 2, etc.)
        for i, record in enumerate(records):
            period_fieldname = f"period_{i+1}"
            
            # Format time for display in cell
            from_time_str = format_time_from_timedelta(record.from_time)
            to_time_str = format_time_from_timedelta(record.to_time)
            time_display = f"({from_time_str})" if from_time_str else ""
            
            # Determine status display
            raw_status = attendance_map.get(record.name)
            if raw_status:
                if raw_status == "Present": status_char = "P"
                elif raw_status == "Absent": status_char = "A"
                elif raw_status == "On Leave": status_char = "L"
                elif raw_status == "Cancelled": status_char = "C"
                else: status_char = raw_status[0].upper() if raw_status else "?"
            else:
                status_char = _("Not marked")
            
            # Combine into cell value: e.g. "P (9:00 am)"
            row[period_fieldname] = f"{status_char} {time_display}"

        data.append(row)

    return data
