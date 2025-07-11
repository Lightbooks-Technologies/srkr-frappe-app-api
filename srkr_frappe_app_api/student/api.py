import frappe
from frappe.utils import today

@frappe.whitelist()
def get_student_course_summary(student):
    """
    Retrieves a list of courses a student is actively enrolled in,
    along with a detailed attendance summary for each course.
    """
    if not student:
        frappe.throw("Student ID is required.")

    # Step 1: Find active Academic Years (Correct)
    today_date = today()
    active_academic_years = frappe.get_all("Academic Year", filters=[["year_start_date", "<=", today_date], ["year_end_date", ">=", today_date]], pluck="name")
    if not active_academic_years: return []

    # Step 2: Get active Program Enrollment names (Correct)
    active_program_enrollments = frappe.get_all("Program Enrollment", filters={"student": student, "academic_year": ["in", active_academic_years], "docstatus": 1}, pluck="name")
    if not active_program_enrollments: return []

    # Step 3: Get enrolled courses from Course Enrollment (Correct, allowing Drafts for now)
    course_enrollment_records = frappe.get_all("Course Enrollment", filters={"program_enrollment": ["in", active_program_enrollments], "docstatus": ["in", [0, 1]]}, fields=["course"], distinct=True)
    if not course_enrollment_records: return []
    
    unique_course_ids = [c.course for c in course_enrollment_records if c.course]
    if not unique_course_ids: return []

    # --- THE FINAL FIX: Bridging Course -> Schedule -> Attendance ---

    # Step 4: Find all Course Schedule documents for the student's courses.
    all_schedules_for_courses = frappe.get_all(
        "Course Schedule",
        filters={"course": ["in", unique_course_ids]},
        fields=["name", "course"]  # We need the schedule's name and the course it belongs to.
    )
    if not all_schedules_for_courses:
        # If there are no schedules, we can't get attendance. Return courses with 0 attendance.
        course_details = frappe.get_all("Course", filters={"name": ["in", unique_course_ids]}, fields=["name", "course_name"])
        course_name_map = {c.name: c.course_name for c in course_details}
        return [
            {"course_id": cid, "course_name": course_name_map.get(cid, cid), "attendance_summary": {"total_classes": 0, "present": 0, "absent": 0, "on_leave": 0}}
            for cid in unique_course_ids
        ]

    # Step 5: Create a map to easily find which course a schedule belongs to.
    # e.g., {'CS-001': 'CS101', 'CS-002': 'CS101', 'MA-001': 'MA203'}
    schedule_to_course_map = {s.name: s.course for s in all_schedules_for_courses}
    relevant_schedule_ids = list(schedule_to_course_map.keys())

    # Step 6: Fetch all attendance records for this student linked to ANY of the relevant schedules.
    all_attendance_records = frappe.get_all(
        "Student Attendance",
        filters={
            "student": student,
            "course_schedule": ["in", relevant_schedule_ids], # <<< This is the correct filter
            "docstatus": 1
        },
        fields=["course_schedule", "status"]
    )

    # Step 7: Initialize the summary and fetch course names.
    course_details = frappe.get_all("Course", filters={"name": ["in", unique_course_ids]}, fields=["name", "course_name"])
    course_name_map = {c.name: c.course_name for c in course_details}
    course_summaries = {}
    for course_id in unique_course_ids:
        course_summaries[course_id] = {"course_id": course_id, "course_name": course_name_map.get(course_id, course_id), "attendance_summary": {"total_classes": 0, "present": 0, "absent": 0, "on_leave": 0}}

    # Step 8: Aggregate the attendance data using our map.
    for att_record in all_attendance_records:
        schedule_id = att_record.course_schedule
        # Find the parent course for this attendance record
        parent_course_id = schedule_to_course_map.get(schedule_id)

        if parent_course_id and parent_course_id in course_summaries:
            summary = course_summaries[parent_course_id]["attendance_summary"]
            summary["total_classes"] += 1
            if att_record.status == "Present": summary["present"] += 1
            elif att_record.status == "Absent": summary["absent"] += 1
            elif att_record.status == "On Leave": summary["on_leave"] += 1

    return list(course_summaries.values())

