import frappe
from frappe import _

def execute(filters=None):
    columns = [
        {"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 100},
        {"fieldname": "course", "label": _("Course"), "fieldtype": "Link", "options": "Course", "width": 250},
        {"fieldname": "instructor", "label": _("Instructor"), "fieldtype": "Data", "width": 200},
        {"fieldname": "student_group", "label": _("Student Group"), "fieldtype": "Link", "options": "Student Group", "width": 200},
        {"fieldname": "from_time", "label": _("Start Time"), "fieldtype": "Time", "width": 100},
        {"fieldname": "to_time", "label": _("End Time"), "fieldtype": "Time", "width": 100},
        {"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120}
    ]

    data = get_data(filters)
    
    return columns, data

def get_data(filters):
    # This query now includes the logic for "Partial" attendance.
    query = """
        SELECT
            cs.schedule_date as date,
            c.course_name as course,
            cs.instructor_name as instructor,
            cs.student_group,
            cs.from_time,
            cs.to_time,
            CASE
                WHEN COUNT(sa.name) = 0 THEN 'Not Taken'
                WHEN COUNT(sa.name) < (SELECT COUNT(*) FROM `tabStudent Group Student` sgs WHERE sgs.parent = cs.student_group AND sgs.active = 1) THEN 'Partial'
                ELSE 'Taken'
            END AS status
        FROM
            `tabCourse Schedule` AS cs
        JOIN `tabCourse` AS c ON cs.course = c.name
        LEFT JOIN `tabStudent Attendance` AS sa ON cs.name = sa.course_schedule
    """
    
    conditions = ["cs.schedule_date = %(date)s"]
    
    if filters.get("instructor"):
        conditions.append("cs.instructor = %(instructor)s")
    
    if filters.get("student_group"):
        conditions.append("cs.student_group = %(student_group)s")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        GROUP BY cs.name
        ORDER BY cs.from_time ASC
    """

    all_data = frappe.db.sql(query, filters, as_dict=1)

    status_filter = filters.get("status")
    if status_filter and status_filter != "All":
        return [row for row in all_data if row.status == status_filter]
    else:
        return all_data