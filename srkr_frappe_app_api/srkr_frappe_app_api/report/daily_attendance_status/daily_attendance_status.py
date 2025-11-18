# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import csv
import io
import datetime

# ====================================================================
# SECTION 1: ORIGINAL REPORT SCRIPT
# ====================================================================

def execute(filters=None):
    columns = get_report_columns()
    data = get_report_data(filters)
    return columns, data

def get_report_columns():
    return [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "program", "label": _("Program"), "fieldtype": "Link", "options": "Program", "width": 200},
        {"fieldname": "course", "label": _("Course"), "fieldtype": "Link", "options": "Course", "width": 250},
        {"fieldname": "instructor", "label": _("Instructor"), "fieldtype": "Data", "width": 200},
        {"fieldname": "student_group", "label": _("Student Group"), "fieldtype": "Link", "options": "Student Group", "width": 200},
        {"fieldname": "from_time", "label": _("Start Time"), "fieldtype": "Time", "width": 100},
        {"fieldname": "to_time", "label": _("End Time"), "fieldtype": "Time", "width": 100},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120}
    ]

def get_report_data(filters):
    """
    OPTIMIZED VERSION: Removed correlated subquery and used JOIN instead.
    The previous version had a subquery that ran for every row, causing massive slowdowns.
    """
    query = """
        SELECT
            cs.schedule_date as date,
            sg.program,
            c.course_name as course,
            cs.instructor_name as instructor,
            cs.student_group,
            cs.from_time,
            cs.to_time,
            CASE
                WHEN COUNT(sa.name) = 0 THEN 'Not Taken'
                WHEN COUNT(sa.name) < COALESCE(sgs.total_students, 0) THEN 'Partial'
                ELSE 'Taken'
            END AS status
        FROM
            `tabCourse Schedule` AS cs
        JOIN `tabCourse` AS c ON cs.course = c.name
        JOIN `tabStudent Group` AS sg ON cs.student_group = sg.name
        LEFT JOIN `tabStudent Attendance` AS sa ON cs.name = sa.course_schedule
        LEFT JOIN (
            SELECT parent, COUNT(*) as total_students 
            FROM `tabStudent Group Student` 
            WHERE active = 1 
            GROUP BY parent
        ) sgs ON cs.student_group = sgs.parent
    """
    conditions = []
    if filters.get("date"): conditions.append("cs.schedule_date = %(date)s")
    if filters.get("program"): conditions.append("sg.program = %(program)s")
    if filters.get("instructor"): conditions.append("cs.instructor = %(instructor)s")
    if filters.get("student_group"): conditions.append("cs.student_group = %(student_group)s")
    if conditions: query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY cs.name, sgs.total_students ORDER BY cs.from_time ASC"
    all_data = frappe.db.sql(query, filters, as_dict=1)
    status_filter = filters.get("status")
    if status_filter and status_filter != "All":
        return [row for row in all_data if row.status == status_filter]
    return all_data

# ====================================================================
# SECTION 2: SCHEDULED EMAIL FUNCTIONALITY
# ====================================================================

def send_daily_attendance_report():
    recipients = ["pramod@lightbooks.io", "prssvraju@srkrec.ac.in", "srkrcse2024@gmail.com", "srkritoffice@gmail.com", "srkraidsoffice@gmail.com", "eceoffice.srkr@gmail.com", "srkreeedepartment@gmail.com", "mechofficesrkr@gmail.com", "srkrhodce@gmail.com", "hodmechsrkr@gmail.com"]
    if not recipients:
        print("ERROR: No recipients are hardcoded in the script.")
        return

    today_string = str(datetime.date.today())
    filters = frappe._dict({"date": today_string})
    
    try:
        columns = get_report_columns()
        data = get_report_data(filters)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Daily Attendance Report Generation Failed")
        print(f"ERROR: Report generation failed - {str(e)}")
        return

    if not data:
        # Using print() here is safe and will show up in the console/logs
        print("INFO: No attendance data for today. Skipping report email.")
        return

    today_formatted = datetime.date.today().strftime("%d %B %Y")
    subject = f"Daily Attendance Status Report - {today_formatted}"
    
    html_content = frappe.render_template(
        "templates/emails/daily_attendance_report.html",
        {"report_date": today_formatted, "columns": columns, "data": data}
    )

    csv_content = create_csv_from_report(columns, data)
    attachment = {"fname": f"daily-attendance-status-{today_string}.csv", "fcontent": csv_content.encode('utf-8')}

    # This is the line that sends the email
    frappe.sendmail(recipients=recipients, subject=subject, message=html_content, attachments=[attachment], now=True)
    
    # THE FINAL FIX: This is now a simple print statement that cannot fail.
    print(f"Daily Attendance Report sent to {', '.join(recipients)}.")


def create_csv_from_report(columns, data):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow([col['label'] for col in columns])
    column_fieldnames = [col['fieldname'] for col in columns]
    for row_dict in data:
        writer.writerow([row_dict.get(fieldname, "") for fieldname in column_fieldnames])
    return csv_buffer.getvalue()

def send_daily_attendance_report_to_main_admin():
    recipients = ["pramod@lightbooks.io", "dean_academics@srkrec.ac.in", "principal@srkrec.ac.in"]
    if not recipients:
        print("ERROR: No recipients are hardcoded in the script.")
        return

    today_string = str(datetime.date.today())
    filters = frappe._dict({"date": today_string})
    
    try:
        columns = get_report_columns()
        data = get_report_data(filters)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Daily Attendance Report Generation Failed")
        print(f"ERROR: Report generation failed - {str(e)}")
        return

    if not data:
        # Using print() here is safe and will show up in the console/logs
        print("INFO: No attendance data for today. Skipping report email.")
        return

    today_formatted = datetime.date.today().strftime("%d %B %Y")
    subject = f"Daily Attendance Status Report Principal and Dean - {today_formatted}"
    
    html_content = frappe.render_template(
        "templates/emails/daily_attendance_report.html",
        {"report_date": today_formatted, "columns": columns, "data": data}
    )

    csv_content = create_csv_from_report(columns, data)
    attachment = {"fname": f"daily-attendance-status-{today_string}.csv", "fcontent": csv_content.encode('utf-8')}

    # This is the line that sends the email
    frappe.sendmail(recipients=recipients, subject=subject, message=html_content, attachments=[attachment], now=True)
    
    # THE FINAL FIX: This is now a simple print statement that cannot fail.
    print(f"Daily Attendance Report sent to {', '.join(recipients)}.")