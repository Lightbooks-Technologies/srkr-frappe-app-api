# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _

# ====================================================================
# CONFIGURATION VARIABLES
# ====================================================================

# Date from which to start calculating attendance for 1st year students
FIRST_YEAR_ATTENDANCE_START_DATE = "2025-09-20"

# Semester patterns to identify 1st year student groups
FIRST_YEAR_SEMESTER_PATTERNS = ["SEM-01", "SEM-02"]

# ====================================================================

def execute(filters=None):
    if not filters or not filters.get("student_group") or not filters.get("course"):
        return [], []

    columns = get_columns(filters)
    if not columns:
        return [], []

    data = get_data(filters, columns)
    
    return columns, data

def is_first_year_group(student_group_name):
    if not student_group_name:
        return False
    for pattern in FIRST_YEAR_SEMESTER_PATTERNS:
        if pattern in student_group_name:
            return True
    return False

def get_columns(filters):
    student_group = filters.get("student_group")
    is_first_year = is_first_year_group(student_group)
    
    date_condition = ""
    if is_first_year:
        date_condition = f"AND schedule_date >= '{FIRST_YEAR_ATTENDANCE_START_DATE}'"
    
    class_schedules = frappe.db.sql(f"""
        SELECT name, schedule_date, from_time
        FROM `tabCourse Schedule`
        WHERE
            student_group = %(student_group)s
            AND course = %(course)s
            {date_condition}
        ORDER BY schedule_date ASC, from_time ASC
    """, filters, as_dict=1)

    if not class_schedules:
        frappe.msgprint(_("No course schedules found for the selected course and student group."))
        return None

    columns = [
        {"fieldname": "sl_no", "label": _("SlNo"), "fieldtype": "Int", "width": 50},
        {"fieldname": "student_id", "label": _("HallTicketNo"), "fieldtype": "Data", "width": 120},
        {"fieldname": "student_name", "label": _("Name"), "fieldtype": "Data", "width": 250},
    ]

    date_periods = {}
    classes_conducted = 0

    for schedule in class_schedules:
        schedule_date = schedule.schedule_date
        date_str = schedule_date.strftime("%Y-%m-%d")
        
        if date_str not in date_periods:
            date_periods[date_str] = 1
        else:
            date_periods[date_str] += 1
            
        period_num = date_periods[date_str]
        classes_conducted += 1
        
        formatted_date = schedule_date.strftime("%d-%b")
        fieldname = "sch_" + schedule.name
        
        # Include Period and Classes Conducted in the label without HTML tags as they get stripped
        label = f"{formatted_date} (P:{period_num} CC:{classes_conducted})"
        
        columns.append({
            "fieldname": fieldname,
            "label": label,
            "fieldtype": "Data",
            "width": 120
        })

    columns.extend([
        {"fieldname": "total_classes", "label": _("T.H"), "fieldtype": "Int", "width": 60},
        {"fieldname": "total_present", "label": _("T.A"), "fieldtype": "Int", "width": 60},
        {"fieldname": "attendance_percentage", "label": _("%"), "fieldtype": "Percent", "width": 80},
    ])

    return columns

def get_data(filters, columns):
    student_group = filters.get("student_group")
    is_first_year = is_first_year_group(student_group)
    
    students = frappe.get_all("Student Group Student",
        filters={"parent": student_group, "active": 1},
        fields=["student", "student_name"]
    )

    if not students:
        return []

    student_ids = [s.student for s in students]
    
    student_filters = {"name": ("in", student_ids)}

    student_details = frappe.get_all("Student",
        filters=student_filters,
        fields=["name", "student_name", "custom_student_id"],
        order_by="custom_student_id ASC"
    )
    
    student_map = {}
    for student in student_details:
        student_map[student.name] = {
            "student_name": student.student_name,
            "custom_student_id": student.custom_student_id or ""
        }

    date_condition = ""
    if is_first_year:
        date_condition = f"AND date >= '{FIRST_YEAR_ATTENDANCE_START_DATE}'"

    attendance_records = frappe.db.sql(f"""
        SELECT student, course_schedule, status
        FROM `tabStudent Attendance`
        WHERE
            student IN %(student_ids)s
            AND student_group = %(student_group)s
            AND course_schedule IN (
                SELECT name FROM `tabCourse Schedule`
                WHERE course = %(course)s
            )
            AND docstatus = 1
            {date_condition}
    """, {"student_ids": student_ids, "student_group": filters.get("student_group"), "course": filters.get("course")}, as_dict=1)

    pivoted_attendance = {}
    for record in attendance_records:
        if record.student not in pivoted_attendance:
            pivoted_attendance[record.student] = {}
        status_char = record.status[0].upper() if record.status else '?'
        pivoted_attendance[record.student][record.course_schedule] = status_char

    final_data = []
    sl_no = 1
    for student in student_details:
        student_info = student_map.get(student.name, {})
        row = {
            "sl_no": sl_no,
            "student_name": student_info.get("student_name", ""),
            "student_id": student_info.get("custom_student_id", ""),
        }
        sl_no += 1
        
        total_present = 0
        total_classes = 0
        cumulative_present = 0
        
        student_attendance_data = pivoted_attendance.get(student.name, {})
        
        for col in columns:
            if col["fieldname"].startswith("sch_"):
                schedule_name = col["fieldname"].replace("sch_", "")
                status = student_attendance_data.get(schedule_name, '-')
                
                # Treat 'not marked' equivalent to absent or blank depending on requirement, 
                # but typically means the student was absent if others were marked, or class didn't happen.
                # Here we only count if marked.
                if status != '-':
                    total_classes += 1
                    if status == 'P':
                        cumulative_present += 1
                        total_present += 1
                        row[col["fieldname"]] = cumulative_present
                    else:
                        row[col["fieldname"]] = "A"
                else:
                    row[col["fieldname"]] = "-"
        
        row["total_classes"] = total_classes
        row["total_present"] = total_present
        row["attendance_percentage"] = (total_present / total_classes * 100) if total_classes > 0 else 0
        
        final_data.append(row)

    return final_data

@frappe.whitelist()
def get_courses_for_student_group(student_group):
    if not student_group:
        return []
    courses = frappe.db.sql("""
        SELECT DISTINCT cs.course, c.course_name
        FROM `tabCourse Schedule` AS cs
        JOIN `tabCourse` AS c ON cs.course = c.name
        WHERE 
            cs.student_group = %(student_group)s
    """, {"student_group": student_group}, as_dict=1)
    return [{"value": c.course, "label": f"{c.course_name} ({c.course})"} for c in courses]
