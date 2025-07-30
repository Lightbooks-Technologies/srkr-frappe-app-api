import frappe
from frappe import _

def execute(filters=None):
    if not filters or not filters.get("student_group"):
        return [], []

    # Get the dynamic columns (Student Info + one for each course)
    columns = get_columns(filters)
    if not columns:
        frappe.msgprint(_("No courses found for the selected Student Group."))
        return [], []

    # Get the processed data rows
    data = get_data(filters, columns)
    
    return columns, data

def get_courses(student_group):
    """Helper function to fetch all unique courses for a student group."""
    return frappe.db.sql("""
        SELECT DISTINCT cs.course, c.course_name
        FROM `tabCourse Schedule` AS cs
        JOIN `tabCourse` AS c ON cs.course = c.name
        WHERE 
            cs.student_group = %(student_group)s
        ORDER BY c.course_name
    """, {"student_group": student_group}, as_dict=1)

def get_columns(filters):
    """Generate dynamic columns: Student Name, Roll No, and one for each course."""
    courses = get_courses(filters.get("student_group"))
    if not courses:
        return None

    # Start with fixed columns
    columns = [
        {"fieldname": "student_name", "label": _("Student Name"), "fieldtype": "Data", "width": 250},
        {"fieldname": "roll_number", "label": _("Roll No"), "fieldtype": "Data", "width": 120},
    ]

    # Add a dynamic column for each course
    for course in courses:
        # Create a safe fieldname from the course ID (e.g., 'MA101' -> 'ma101')
        fieldname = course.course.lower().replace("-", "_").replace(" ", "_")
        columns.append({
            "fieldname": fieldname,
            "label": course.course_name,
            "fieldtype": "Percent",
            "width": 150,
            "precision": 2,
            # We store the original course ID here for easy lookup later
            "options": course.course 
        })
    
    return columns

def get_data(filters, columns):
    """
    Fetch and process attendance data to calculate term-end percentages.
    """
    student_group = filters.get("student_group")

    # 1. Get all students in the group
    students = frappe.get_all("Student Group Student",
        filters={"parent": student_group, "active": 1},
        fields=["student", "student_name", "group_roll_number"],
        order_by="group_roll_number"
    )
    if not students:
        return []

    # 2. Get all attendance data for the entire group in one efficient query.
    # This query groups by student and course, and calculates the summary stats directly.
    attendance_summary = frappe.db.sql("""
        SELECT
            sa.student,
            cs.course,
            SUM(CASE WHEN sa.status = 'Present' THEN 1 ELSE 0 END) as present_count,
            COUNT(sa.name) as total_count
        FROM
            `tabStudent Attendance` AS sa
        JOIN `tabCourse Schedule` AS cs ON sa.course_schedule = cs.name
        WHERE
            sa.student_group = %(student_group)s
            AND sa.docstatus = 1
        GROUP BY
            sa.student, cs.course
    """, {"student_group": student_group}, as_dict=1)

    # 3. Pivot the summary data into an easy-to-access structure:
    # { student_id: { course_id: percentage, ... }, ... }
    pivoted_data = {}
    for summary in attendance_summary:
        if summary.student not in pivoted_data:
            pivoted_data[summary.student] = {}
        
        percentage = 0.0
        if summary.total_count > 0:
            percentage = round((summary.present_count / summary.total_count) * 100, 2)
        
        pivoted_data[summary.student][summary.course] = percentage

    # 4. Build the final data rows for the report
    final_data = []
    for student in students:
        row = {
            "student_name": student.student_name,
            "roll_number": student.group_roll_number
        }
        
        student_performance = pivoted_data.get(student.student, {})

        # Populate the dynamic course columns
        for col in columns:
            # We check for the 'options' field where we stored the course ID
            if col.get("options"):
                course_id = col.get("options")
                # Get the percentage for that course, defaulting to 0.0
                percentage = student_performance.get(course_id, 0.0)
                row[col.get("fieldname")] = percentage
        
        final_data.append(row)

    return final_data