# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
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


def execute(filters=None):
    """
    Generate cumulative attendance report for students in a semester
    Shows total attendance across all classes in the academic year/term
    UPDATED: Filters attendance for 1st year students to only include dates from configured start date onwards.
    """
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "student",
            "label": _("Student ID"),
            "fieldtype": "Link",
            "options": "Student",
            "width": 120
        },
        {
            "fieldname": "student_name",
            "label": _("Student Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "custom_student_id",
            "label": _("Custom Student ID"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "group_roll_number",
            "label": _("Roll Number"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "classes_attended",
            "label": _("Classes Attended"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "total_classes",
            "label": _("Total Classes"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "attendance_percentage",
            "label": _("Attendance %"),
            "fieldtype": "Percent",
            "width": 120
        }
    ]


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


def get_data(filters):
    """
    Get attendance data for students
    UPDATED: Filters attendance for 1st year students based on start date.
    """
    
    if not filters.get("student_group"):
        frappe.msgprint(_("Please select a Student Group"))
        return []
    
    student_group = filters.get("student_group")
    gender = filters.get("gender")
    hostel_opt_in = filters.get("hostel_opt_in")
    
    # Check if this is a first year group
    is_first_year = is_first_year_group(student_group)
    
    # Step 1: Get student group details to extract academic year and term
    student_group_doc = frappe.get_doc("Student Group", student_group)
    academic_year = student_group_doc.academic_year
    academic_term = student_group_doc.academic_term
    
    if not academic_year:
        frappe.msgprint(_("Student Group does not have an Academic Year assigned"))
        return []
    
    # Step 2: Get all students in the selected group
    StudentGroupStudent = frappe.qb.DocType("Student Group Student")
    Student = frappe.qb.DocType("Student")
    
    students_query = (
        frappe.qb.from_(StudentGroupStudent)
        .left_join(Student)
        .on(StudentGroupStudent.student == Student.name)
        .select(
            StudentGroupStudent.student,
            StudentGroupStudent.student_name,
            StudentGroupStudent.group_roll_number,
            Student.custom_student_id
        )
        .where(
            (StudentGroupStudent.parent == student_group)
            & (StudentGroupStudent.active == 1)
        )
    )

    if gender:
        students_query = students_query.where(Student.gender == gender)
    
    if hostel_opt_in:
        if hostel_opt_in == "Yes":
           students_query = students_query.where(Student.custom_hostel_required == 1)
        elif hostel_opt_in == "No":
           students_query = students_query.where(Student.custom_hostel_required == 0)

    students_query = students_query.orderby(StudentGroupStudent.group_roll_number)
    
    students_list = students_query.run(as_dict=True)
    
    if not students_list:
        frappe.msgprint(_("No active students found in this Student Group"))
        return []
    
    student_ids = [s.student for s in students_list]
    
    # Step 3: Find ALL Student Groups with the same academic year and term
    # This gives us all groups the students might be enrolled in for this semester
    StudentGroup = frappe.qb.DocType("Student Group")
    
    student_groups_query = (
        frappe.qb.from_(StudentGroup)
        .select(StudentGroup.name)
        .where(StudentGroup.academic_year == academic_year)
    )
    
    # Add academic term filter if present
    if academic_term:
        student_groups_query = student_groups_query.where(StudentGroup.academic_term == academic_term)
    
    semester_student_groups = [sg.name for sg in student_groups_query.run(as_dict=True)]
    
    if not semester_student_groups:
        return format_students_with_zero_attendance(students_list)
    
    # Step 5: Get student group memberships for our students in this semester
    student_memberships = frappe.get_all(
        "Student Group Student",
        filters={
            "student": ["in", student_ids],
            "active": 1,
            "parent": ["in", semester_student_groups]
        },
        fields=["student", "parent"]
    )
    
    student_to_groups = {}
    for m in student_memberships:
        if m.student not in student_to_groups:
            student_to_groups[m.student] = set()
        student_to_groups[m.student].add(m.parent)

    # Step 6: Get group to schedules mapping (only those with submitted attendance)
    # This prevents counting future classes or classes where attendance wasn't taken
    CourseSchedule = frappe.qb.DocType("Course Schedule")
    StudentAttendance = frappe.qb.DocType("Student Attendance")
    
    schedules_query = (
        frappe.qb.from_(CourseSchedule)
        .join(StudentAttendance).on(StudentAttendance.course_schedule == CourseSchedule.name)
        .select(CourseSchedule.name, CourseSchedule.student_group)
        .where(CourseSchedule.student_group.isin(semester_student_groups))
        .where(StudentAttendance.docstatus == 1)
        .where(CourseSchedule.schedule_date <= frappe.utils.today())
    )
    
    if is_first_year:
        schedules_query = schedules_query.where(
            CourseSchedule.schedule_date >= FIRST_YEAR_ATTENDANCE_START_DATE
        )
    
    all_course_schedules = schedules_query.distinct().run(as_dict=True)
    
    group_to_schedules = {}
    all_schedule_ids = []
    for cs in all_course_schedules:
        all_schedule_ids.append(cs.name)
        if cs.student_group not in group_to_schedules:
            group_to_schedules[cs.student_group] = set()
        group_to_schedules[cs.student_group].add(cs.name)

    if not all_schedule_ids:
        # No schedules found, return students with zero attendance
        return format_students_with_zero_attendance(students_list)
    
    # Step 7: Get attendance records for our students across relevant schedules
    StudentAttendance = frappe.qb.DocType("Student Attendance")
    
    attendance_query = (
        frappe.qb.from_(StudentAttendance)
        .select(
            StudentAttendance.student,
            StudentAttendance.course_schedule,
            StudentAttendance.status,
            StudentAttendance.date
        )
        .where(
            (StudentAttendance.student.isin(student_ids))
            & (StudentAttendance.course_schedule.isin(all_schedule_ids))
            & (StudentAttendance.docstatus == 1)
        )
    )
    
    # Add date filter for first year groups (additional safety)
    if is_first_year:
        attendance_query = attendance_query.where(
            StudentAttendance.date >= FIRST_YEAR_ATTENDANCE_START_DATE
        )
    
    attendance_records = attendance_query.run(as_dict=True)
    
    # Step 8: Process attendance data
    return process_attendance_data(students_list, attendance_records, student_to_groups, group_to_schedules)


def process_attendance_data(students_list, attendance_records, student_to_groups, group_to_schedules):
    """Process attendance records and calculate statistics"""
    
    # Create a mapping of student to their attendance records
    student_attendance_map = {}
    for record in attendance_records:
        student = record.student
        if student not in student_attendance_map:
            student_attendance_map[student] = {
                'attended': set(),
                'total': set()
            }
        
        # Add this schedule to total classes for this student
        student_attendance_map[student]['total'].add(record.course_schedule)
        
        # If status is Present, add to attended
        if record.status == "Present":
            student_attendance_map[student]['attended'].add(record.course_schedule)
    
    # Build result data
    result = []
    for student in students_list:
        student_id = student.student
        
        # Calculate expected total classes based on student's group memberships in this semester
        expected_schedules = set()
        student_groups = student_to_groups.get(student_id, set())
        for group in student_groups:
            expected_schedules.update(group_to_schedules.get(group, set()))
        
        # Merge with schedules from actual attendance records (ensures consistency)
        actual_schedules = set()
        attended_count = 0
        
        if student_id in student_attendance_map:
            attended_count = len(student_attendance_map[student_id]['attended'])
            actual_schedules = student_attendance_map[student_id]['total']
        
        total_schedules_set = expected_schedules.union(actual_schedules)
        total_count = len(total_schedules_set)
        
        # Calculate percentage
        if total_count > 0:
            percentage = (attended_count / total_count) * 100
        else:
            percentage = 0
        
        result.append({
            'student': student_id,
            'student_name': student.student_name,
            'custom_student_id': student.custom_student_id,
            'group_roll_number': student.group_roll_number,
            'classes_attended': attended_count,
            'total_classes': total_count,
            'attendance_percentage': percentage
        })
    
    return result


def format_students_with_zero_attendance(students_list):
    """Format students with no attendance records"""
    result = []
    for student in students_list:
        result.append({
            'student': student.student,
            'student_name': student.student_name,
            'custom_student_id': student.custom_student_id,
            'group_roll_number': student.group_roll_number,
            'classes_attended': 0,
            'total_classes': 0,
            'attendance_percentage': 0
        })
    return result