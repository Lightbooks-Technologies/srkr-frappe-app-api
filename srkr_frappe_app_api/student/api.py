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

@frappe.whitelist()
def get_course_schedule_for_student(program_name, student_groups, from_date=None, to_date=None):
    """
    Retrieves the course schedule for a student based on program and student groups,
    with optional date range filtering.
    """
    # If student_groups is passed as a string (JSON), parse it
    if isinstance(student_groups, str):
        import json
        student_groups = json.loads(student_groups)
    
    student_group_list = [sg.get("label") for sg in student_groups]

    filters = {
        "program": program_name, 
        "student_group": ["in", student_group_list]
    }

    if from_date and to_date:
        filters["schedule_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["schedule_date"] = [">=", from_date]
    elif to_date:
        filters["schedule_date"] = ["<=", to_date]

    schedule = frappe.db.get_list(
        "Course Schedule",
        fields=[
            "schedule_date", 
            "room", 
            "class_schedule_color", 
            "course", 
            "from_time", 
            "to_time", 
            "instructor", 
            "title", 
            "name"
        ],
        filters=filters,
        order_by="schedule_date asc",
    )
    return schedule

@frappe.whitelist()
def get_student_info():
    """
    Fetches information for the currently logged-in user if they are linked to a Student record.
    Returns specific fields including 'student_id' and 'student_name'.
    """
    current_user_email = frappe.session.user

    if current_user_email == "Administrator":
        return {"message": "Administrator account. No specific student profile to display."}

    # Find Student record linked to this User
    # 1. Check 'user' field
    # 2. Fallback to 'student_email_id'
    student_found = frappe.get_all(
        "Student",
        filters=[
            ["user", "=", current_user_email],
            ["enabled", "=", 1]
        ],
        fields=["name", "student_name", "first_name", "last_name", "image", "student_email_id"],
        limit=1
    )

    if not student_found:
        student_found = frappe.get_all(
            "Student",
            filters=[
                ["student_email_id", "=", current_user_email],
                ["enabled", "=", 1]
            ],
            fields=["name", "student_name", "first_name", "last_name", "image", "student_email_id"],
            limit=1
        )

    if student_found:
        student = student_found[0]
        # Get active Program Enrollment for additional context
        enrollment = frappe.get_all(
            "Program Enrollment",
            filters={"student": student.name, "docstatus": 1},
            fields=["program", "academic_year", "academic_term", "current_semester"],
            order_by="creation desc",
            limit=1
        )
        
        student_info = {
            "student_id": student.name,
            "student_name": student.student_name,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "email": student.student_email_id,
            "image": student.image,
            "enrollment": enrollment[0] if enrollment else None
        }
        return student_info
    else:
        return {"message": f"No active Student record found linked to user {current_user_email}."}

@frappe.whitelist()
def get_my_mentorship_logs():
    """
    Automatically identifies the logged-in student and returns their mentorship logs.
    """
    student_info = get_student_info()
    if "student_id" not in student_info:
        frappe.throw(student_info.get("message", "Could not identify student."))
    
    return get_mentorship_logs(student_info["student_id"])

@frappe.whitelist()
def get_mentorship_logs(student):
    """
    Get all mentorship log entries for a specific student.
    :param student: The ID of the student (e.g., "EDU-STU-2025-00119").
    """
    if not student:
        frappe.throw("Parameter 'student' is required.")

    return frappe.get_all(
        "Mentorship Log Entry",
        filters={"student": student},
        fields=["name", "date", "mentor", "academic_term"],
        order_by="date desc"
    )


@frappe.whitelist()
def get_mentorship_log_details(log_id):
    """
    Get the full details of a single mentorship log entry for a student.
    :param log_id: The unique name/ID of the Mentorship Log Entry document.
    """
    if not log_id:
        frappe.throw("Parameter 'log_id' is required.")
        
    try:
        # Fetch the log and return as dict
        log_entry = frappe.get_doc("Mentorship Log Entry", log_id).as_dict()
        
        # Optional: Add security check here if needed to ensure the student
        # is only viewing their own logs.
        
        return log_entry
    except frappe.DoesNotExistError:
        frappe.throw(f"Mentorship Log Entry with ID '{log_id}' not found.", frappe.NotFound)


