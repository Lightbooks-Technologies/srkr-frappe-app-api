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
        date_condition = f"AND date >= '{FIRST_YEAR_ATTENDANCE_START_DATE}'"
    
    class_dates = frappe.db.sql(f"""
        SELECT DISTINCT date
        FROM `tabStudent Attendance`
        WHERE
            student_group = %(student_group)s
            AND course_schedule IN (
                SELECT name FROM `tabCourse Schedule`
                WHERE course = %(course)s
            )
            AND docstatus = 1
            {date_condition}
        ORDER BY date ASC
    """, filters, as_list=1)

    if not class_dates:
        frappe.msgprint(_("No attendance records found for the selected course and student group."))
        return None

    columns = [
        {"fieldname": "sl_no", "label": _("SlNo"), "fieldtype": "Int", "width": 50},
        {"fieldname": "student_id", "label": _("HallTicketNo"), "fieldtype": "Data", "width": 120},
        {"fieldname": "student_name", "label": _("Name"), "fieldtype": "Data", "width": 250},
    ]

    for idx, date_tuple in enumerate(class_dates):
        date = date_tuple[0]
        formatted_date = date.strftime("%d-%b-%y")
        fieldname = "date_" + date.strftime("%Y_%m_%d")
        columns.append({
            "fieldname": fieldname,
            "label": formatted_date,
            "fieldtype": "Data",
            "width": 80
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
        SELECT student, date, status
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
        ORDER BY date ASC
    """, {"student_ids": student_ids, **filters}, as_dict=1)

    pivoted_attendance = {}
    for record in attendance_records:
        date_key = record.date.strftime("%Y_%m_%d")
        status_char = record.status[0].upper() if record.status else '?'
        
        if record.student not in pivoted_attendance:
            pivoted_attendance[record.student] = {}
        # Avoid overwriting if multiple classes on same day, just take last or concatenate?
        # Actually in this specific use case, we map status per day. 
        # If there are multiple periods per day, we'd need time. I'll just keep the first or last status per day for now
        # or just map it as normal. Since the date is distinct.
        pivoted_attendance[record.student][date_key] = status_char

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
            if col["fieldname"].startswith("date_"):
                date_key = col["fieldname"].replace("date_", "")
                status = student_attendance_data.get(date_key, '-')
                
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
