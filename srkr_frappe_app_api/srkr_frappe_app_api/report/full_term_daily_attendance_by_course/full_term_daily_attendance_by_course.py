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
# If a student group name contains any of these patterns, it's considered 1st year
FIRST_YEAR_SEMESTER_PATTERNS = ["SEM-01", "SEM-02"]

# ====================================================================

TEACHING_ROLE_PROFILE = "SRKR Teaching Employee Profile"


def is_teaching_staff():
    user = frappe.session.user
    if user in ("Administrator", "Guest"):
        return False
    return frappe.db.get_value("User", user, "role_profile_name") == TEACHING_ROLE_PROFILE


def get_current_instructor():
    user = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
    if not employee:
        return None
    return frappe.db.get_value("Instructor", {"employee": employee}, "name")


def get_instructor_allowed_groups(instructor):
    """Return set of student_group names the instructor has Course Schedules in."""
    if not instructor:
        return None
    rows = frappe.db.sql("""
        SELECT DISTINCT student_group
        FROM `tabCourse Schedule`
        WHERE instructor = %(instructor)s
    """, {"instructor": instructor}, as_list=True)
    return {r[0] for r in rows}


def execute(filters=None):
    if not filters or not filters.get("student_group") or not filters.get("course"):
        return [], []

    if is_teaching_staff():
        instructor = get_current_instructor()
        allowed = get_instructor_allowed_groups(instructor)
        if allowed is not None and filters.get("student_group") not in allowed:
            frappe.throw(_("You are not authorised to view attendance for this student group."))

    columns = get_columns(filters)
    if not columns:
        return [], []

    data = get_data(filters, columns)
    
    return columns, data

def is_first_year_group(student_group_name):
    """
    Check if the student group is a first year group based on configured patterns.
    """
    if not student_group_name:
        return False
    
    for pattern in FIRST_YEAR_SEMESTER_PATTERNS:
        if pattern in student_group_name:
            return True
    return False

def get_columns(filters):
    """
    Generate dynamic columns: Student Info, one column for each class date, and summary columns.
    UPDATED: Filter out dates before the first year start date for first year groups.
    """
    student_group = filters.get("student_group")
    is_first_year = is_first_year_group(student_group)
    
    # Build the date filter condition
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
        {"fieldname": "student_name", "label": _("Student Name"), "fieldtype": "Data", "width": 200},
        {"fieldname": "student_id", "label": _("Student Id"), "fieldtype": "Data", "width": 100},
    ]

    for date_tuple in class_dates:
        date = date_tuple[0]
        formatted_date = date.strftime("%d-%m")
        fieldname = "date_" + date.strftime("%Y_%m_%d")
        columns.append({
            "fieldname": fieldname,
            "label": formatted_date,
            "fieldtype": "Data",
            "width": 60
        })

    columns.extend([
        {"fieldname": "total_present", "label": _("Total Present"), "fieldtype": "Int", "width": 120},
        {"fieldname": "total_classes", "label": _("Total Classes"), "fieldtype": "Int", "width": 120},
        {"fieldname": "attendance_percentage", "label": _("Attendance %"), "fieldtype": "Percent", "width": 120},
    ])

    return columns

def get_data(filters, columns):
    """
    Fetch and pivot the attendance data to match the dynamic columns.
    UPDATED: Filter out attendance records before the first year start date for first year groups.
    """
    student_group = filters.get("student_group")
    gender = filters.get("gender")
    hostel_opt_in = filters.get("hostel_opt_in")
    is_first_year = is_first_year_group(student_group)
    
    # Get students from Student Group Student - REMOVE the problematic order_by
    students = frappe.get_all("Student Group Student",
        filters={"parent": student_group, "active": 1},
        fields=["student", "student_name"]
    )

    if not students:
        return []

    # Get student IDs for further queries
    student_ids = [s.student for s in students]
    
    # Prepare student filters
    student_filters = {"name": ("in", student_ids)}
    if gender:
        student_filters["gender"] = gender
    
    if hostel_opt_in:
        if hostel_opt_in == "Yes":
            student_filters["custom_hostel_required"] = 1
        elif hostel_opt_in == "No":
            student_filters["custom_hostel_required"] = 0

    # Get student details including custom_student_id from Student doctype
    student_details = frappe.get_all("Student",
        filters=student_filters,
        fields=["name", "student_name", "custom_student_id"],
        order_by="custom_student_id ASC"  # Order by custom_student_id here instead
    )
    
    # Create a mapping of student details
    student_map = {}
    for student in student_details:
        student_map[student.name] = {
            "student_name": student.student_name,
            "custom_student_id": student.custom_student_id or ""
        }

    # Build the date filter condition
    date_condition = ""
    if is_first_year:
        date_condition = f"AND date >= '{FIRST_YEAR_ATTENDANCE_START_DATE}'"

    # Get attendance records
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
    """, {"student_ids": student_ids, **filters}, as_dict=1)

    # Create pivoted attendance data
    pivoted_attendance = {}
    for record in attendance_records:
        date_key = record.date.strftime("%Y_%m_%d")
        status_char = record.status[0].upper() if record.status else '?'
        
        if record.student not in pivoted_attendance:
            pivoted_attendance[record.student] = {}
        pivoted_attendance[record.student][date_key] = status_char

    # Build final data using the ordered student_details
    final_data = []
    for student in student_details:  # This is already ordered by custom_student_id
        student_info = student_map.get(student.name, {})
        row = {
            "student_name": student_info.get("student_name", ""),
            "student_id": student_info.get("custom_student_id", ""),
        }
        
        total_present = 0
        total_classes = 0
        
        student_attendance_data = pivoted_attendance.get(student.name, {})
        
        # Process each date column
        for col in columns:
            if col["fieldname"].startswith("date_"):
                date_key = col["fieldname"].replace("date_", "")
                status = student_attendance_data.get(date_key, '-')
                row[col["fieldname"]] = status
                
                if status != '-':
                    total_classes += 1
                    if status == 'P':
                        total_present += 1
        
        row["total_present"] = total_present
        row["total_classes"] = total_classes
        row["attendance_percentage"] = (total_present / total_classes * 100) if total_classes > 0 else 0
        
        final_data.append(row)

    return final_data

@frappe.whitelist()
def get_courses_for_student_group(student_group):
    """
    A whitelisted API to fetch courses for the dynamic filter.
    For teaching staff, only returns courses they personally teach in that group.
    """
    if not student_group:
        return []

    conditions = ["cs.student_group = %(student_group)s"]
    values = {"student_group": student_group}

    if is_teaching_staff():
        instructor = get_current_instructor()
        if instructor:
            conditions.append("cs.instructor = %(instructor)s")
            values["instructor"] = instructor

    where = " AND ".join(conditions)

    courses = frappe.db.sql("""
        SELECT DISTINCT cs.course, c.course_name
        FROM `tabCourse Schedule` AS cs
        JOIN `tabCourse` AS c ON cs.course = c.name
        WHERE {where}
    """.format(where=where), values, as_dict=1)

    return [{"value": c.course, "label": f"{c.course_name} ({c.course})"} for c in courses]