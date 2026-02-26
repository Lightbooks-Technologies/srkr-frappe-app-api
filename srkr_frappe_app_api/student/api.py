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

@frappe.whitelist()
def get_student_attendance(student):
    """
    Returns attendance stats for the logged-in student across all semesters.

    Response shape:
    {
        "current_semester": {
            "semester": "SEM-03",
            "group": "BTECH-EEE-AY2526-SEM-03-A",
            "overall_percentage": 85.0,
            "attended": 370,
            "total": 440,
            "courses": [
                {"course_name": "...", "percentage": 93.1, "attended": 54, "total": 58}
            ]
        },
        "history": [
            {"semester": "SEM-02", "group": "BTECH-EEE-AY2526-SEM-02-A", "overall_percentage": 78.5, "attended": 266, "total": 340},
        ]
    }
    """
    if not student:
        frappe.throw("Parameter 'student' is required.")

    try:
        # --- Step 1: Get current_semester from Program Enrollment ---
        current_semester = frappe.db.get_value(
            "Program Enrollment",
            {"student": student},
            "current_semester"
        )

        if not current_semester:
            frappe.throw(f"No Program Enrollment found for student '{student}'.")

        # --- Step 2: Get all base groups for this student across all semesters ---
        # For each semester, pick the group with the shortest name (base group).
        # Subgroups always extend the base group name, so shortest = base.
        all_group_rows = frappe.db.sql("""
            SELECT
                sg.name AS group_name,
                sg.program_semester,
                sg.academic_year
            FROM `tabStudent Group Student` sgs
            JOIN `tabStudent Group` sg ON sg.name = sgs.parent
            WHERE sgs.student = %(student)s
            AND sgs.active = 1
            AND sg.disabled = 0
            ORDER BY sg.program_semester, LENGTH(sg.name) ASC
        """, {"student": student}, as_dict=True)

        # Keep only the first (shortest-named) group per semester
        semester_to_group = {}
        for row in all_group_rows:
            if row.program_semester not in semester_to_group:
                semester_to_group[row.program_semester] = row

        if not semester_to_group:
            return {"current_semester": None, "history": []}

        # --- Step 3: Separate current group from historical groups ---
        current_group_info = semester_to_group.get(current_semester)
        past_groups = [
            info for sem, info in semester_to_group.items()
            if sem != current_semester
        ]

        # --- Helper: Calculate attendance for a single group scoped to one student ---
        def get_attendance_for_group(group_name, with_course_breakdown=False):
            """
            Returns attendance stats for a student in a given group.
            If with_course_breakdown=True, also returns per-course stats.
            """
            # Get all course schedules for this group
            course_schedules = frappe.get_all(
                "Course Schedule",
                filters={"student_group": group_name},
                fields=["name", "course"]
            )

            if not course_schedules:
                result = {"attended": 0, "total": 0, "overall_percentage": None}
                if with_course_breakdown:
                    result["courses"] = []
                return result

            all_schedule_ids = [cs.name for cs in course_schedules]

            # Get all submitted attendance records for this student in this group
            attendance_records = frappe.get_all(
                "Student Attendance",
                filters={
                    "student": student,
                    "course_schedule": ["in", all_schedule_ids],
                    "docstatus": 1
                },
                fields=["course_schedule", "status"]
            )

            # Build a lookup: schedule_id -> status
            schedule_status = {r.course_schedule: r.status for r in attendance_records}

            # --- Overall stats ---
            total = len(all_schedule_ids)
            attended = sum(1 for cs in course_schedules if schedule_status.get(cs.name) == "Present")
            overall_percentage = round((attended / total) * 100, 2) if total > 0 else None

            result = {
                "attended": attended,
                "total": total,
                "overall_percentage": overall_percentage
            }

            if not with_course_breakdown:
                return result

            # --- Course-wise breakdown ---
            # Get course names
            course_ids = list(set(cs.course for cs in course_schedules if cs.course))
            course_details = frappe.get_all(
                "Course",
                filters={"name": ["in", course_ids]},
                fields=["name", "course_name"]
            )
            course_name_map = {c.name: c.course_name for c in course_details}

            # Group schedules by course
            course_to_schedules = {}
            for cs in course_schedules:
                if cs.course:
                    course_to_schedules.setdefault(cs.course, []).append(cs.name)

            courses = []
            for course_id, schedule_ids in course_to_schedules.items():
                c_total = len(schedule_ids)
                c_attended = sum(1 for sid in schedule_ids if schedule_status.get(sid) == "Present")
                c_percentage = round((c_attended / c_total) * 100, 2) if c_total > 0 else None
                courses.append({
                    "course_name": course_name_map.get(course_id, course_id),
                    "percentage": c_percentage,
                    "attended": c_attended,
                    "total": c_total
                })

            # Sort courses by name for consistent ordering
            courses.sort(key=lambda x: x["course_name"])
            result["courses"] = courses
            return result

        # --- Step 4: Build current semester response ---
        current_data = None
        if current_group_info:
            stats = get_attendance_for_group(current_group_info.group_name, with_course_breakdown=True)
            current_data = {
                "semester": current_semester,
                "group": current_group_info.group_name,
                **stats
            }

        # --- Step 5: Build history response ---
        history = []
        for group_info in past_groups:
            stats = get_attendance_for_group(group_info.group_name, with_course_breakdown=False)
            history.append({
                "semester": group_info.program_semester,
                "group": group_info.group_name,
                **stats
            })

        # Sort history by semester descending (SEM-04 before SEM-03 etc.)
        history.sort(key=lambda x: x["semester"], reverse=True)

        return {
            "current_semester": current_data,
            "history": history
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_student_attendance API Error")
        frappe.throw(f"An error occurred: {e}")

@frappe.whitelist()
def get_my_exam_results():
    """
    Automatically identifies the logged-in student and returns their exam results.
    """
    student_info = get_student_info()
    if "student_id" not in student_info:
        frappe.throw(student_info.get("message", "Could not identify student."))
    
    return get_student_exam_results(student_info["student_id"])

@frappe.whitelist()
def get_student_exam_results(student):
    """
    Get all exam semester results for a specific student, including subject-wise results.
    """
    if not student:
        frappe.throw("Parameter 'student' is required.")

    # Fetch the parent documents
    semester_results = frappe.get_all(
        "Exam Semester Result",
        filters={"student": student},
        fields=[
            "name", "semester_number", "sgpa", "cgpa", "exam_status", 
            "total_credits", "credits_secured", "pending_subjects"
        ],
        order_by="semester_number asc"
    )

    if not semester_results:
        return []

    # Prepare list of result names to fetch child records in bulk
    result_names = [r["name"] for r in semester_results]

    # Fetch child documents
    subject_results = frappe.get_all(
        "Exam Subject Result",
        filters={"parent": ["in", result_names], "parenttype": "Exam Semester Result", "parentfield": "subjects"},
        fields=[
            "parent", "subject_code", "subject_name", "credits", "grade", "result", "exammy", "course"
        ],
        order_by="idx asc"
    )

    # Group subject results by parent
    from collections import defaultdict
    subjects_by_parent = defaultdict(list)
    for sub in subject_results:
        parent = sub.pop("parent")
        subjects_by_parent[parent].append(sub)

    # Attach subjects to their respective semester results
    for sem_result in semester_results:
        sem_result["subjects"] = subjects_by_parent.get(sem_result["name"], [])

    return semester_results

