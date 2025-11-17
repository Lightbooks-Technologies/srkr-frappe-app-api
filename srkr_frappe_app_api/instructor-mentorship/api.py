import frappe
from frappe.utils import today


@frappe.whitelist()
def get_mentorship_students(instructor):
    """
    Retrieves a list of all Student Mentorship Profiles assigned to a specific instructor.
    
    Includes cumulative attendance percentage for each student based on their 
    active Student Group and all associated Course Schedules.
    """
    if not instructor:
        return []

    try:
        # --- Step 1: Get the base list of students for the mentor ---
        student_profiles = frappe.get_all(
            "Student Mentorship Profile",
            filters={"current_mentor": instructor},
            fields=["name", "student", "student_name", "program"],
            order_by="student_name asc"
        )
        
        if not student_profiles:
            return []

        # --- Step 2: Get active Student Groups for all students ---
        student_ids = [p["student"] for p in student_profiles]
        
        # Get active student group mappings
        student_group_mappings = frappe.get_all(
            "Student Group Student",
            filters={
                "student": ["in", student_ids],
                "active": 1
            },
            fields=["student", "parent"]  # parent is the Student Group name
        )
        
        # Create a map of student -> student_group
        student_to_group = {sg.student: sg.parent for sg in student_group_mappings}
        
        # Get all unique student groups
        student_groups = list(set(student_to_group.values()))
        
        if not student_groups:
            # No active student groups found
            for profile in student_profiles:
                profile["cumulative_attendance"] = None
            return student_profiles

        # --- Step 3: Get all Course Schedules for these Student Groups ---
        course_schedules = frappe.get_all(
            "Course Schedule",
            filters={"student_group": ["in", student_groups]},
            pluck="name"
        )
        
        if not course_schedules:
            # No course schedules found
            for profile in student_profiles:
                profile["cumulative_attendance"] = None
            return student_profiles

        # --- Step 4: Get all attendance records ---
        attendance_records = frappe.get_all(
            "Student Attendance",
            filters={
                "student": ["in", student_ids],
                "course_schedule": ["in", course_schedules],
                "docstatus": 1
            },
            fields=["student", "status"]
        )

        # --- Step 5: Calculate attendance for each student ---
        attendance_summary = {sid: {"present": 0, "total": 0} for sid in student_ids}
        
        for record in attendance_records:
            if record.student in attendance_summary:
                attendance_summary[record.student]["total"] += 1
                if record.status == "Present":
                    attendance_summary[record.student]["present"] += 1
        
        # --- Step 6: Add attendance percentage to each profile ---
        for profile in student_profiles:
            student_id = profile["student"]
            summary = attendance_summary.get(student_id)
            
            if summary and summary["total"] > 0:
                percentage = round((summary["present"] / summary["total"]) * 100, 2)
                profile["cumulative_attendance"] = percentage
            else:
                profile["cumulative_attendance"] = None

        return student_profiles

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_mentorship_students API Error")
        return []
@frappe.whitelist()
def get_mentorship_logs_by_student(student):
    """
    API Endpoint 1: Get all mentorship log entries for a specific student.
    :param student: The ID of the student (e.g., "EDU-STU-2025-00119").
    """
    if not student:
        frappe.throw("Parameter 'student' is required.")

    return frappe.get_all(
        "Mentorship Log Entry",
        filters={"student": student},
        fields=["name", "date", "mentor", "academic_term"],
        order_by="date desc"  # Show most recent first
    )

@frappe.whitelist()
def get_mentorship_log_details(log_id):
    """
    API Endpoint 2: Get the full details of a single mentorship log entry.
    :param log_id: The unique name/ID of the Mentorship Log Entry document.
    """
    if not log_id:
        frappe.throw("Parameter 'log_id' is required.")
        
    try:
        # frappe.get_doc returns the entire document as a dictionary
        return frappe.get_doc("Mentorship Log Entry", log_id).as_dict()
    except frappe.DoesNotExistError:
        frappe.throw(f"Mentorship Log Entry with ID '{log_id}' not found.", frappe.NotFound)

@frappe.whitelist(methods=["POST"])
def create_mentorship_log_entry(**kwargs):
    """
    API Endpoint 3: Creates a new Mentorship Log Entry.
    Accepts all fields of the DocType as keyword arguments.
    
    IMPROVEMENT: This version automatically converts integer ratings (1-5) 
    into the float format (0.2-1.0) that Frappe requires.
    """
    # --- 1. Validate Required Fields ---
    required_fields = ['student', 'mentor']
    for field in required_fields:
        if not kwargs.get(field):
            frappe.throw(f"Required field missing: '{field}'")

    # --- 2. Build the Document Dictionary ---
    log_data = {
        "doctype": "Mentorship Log Entry",
        "student": kwargs.get('student'),
        "mentor": kwargs.get('mentor'),
        "date": kwargs.get('date', today()) # Default to today if not provided
    }

    # --- 3. Add Optional Fields and Handle Ratings ---
    optional_fields = [
        'academic_term', 'notes', 'teaching_quality_rating', 'facilities_rating',
        'subject_struggles', 'subject_struggles_notes', 'content_relevancy_rating',
        'assessment_rating', 'academic_concerns_summary', 'hostel_rating',
        'food_rating', 'issue_hostel_cleanliness', 'issue_hostel_wifi',
        'issue_food_quality', 'transport_rating', 'sports_rating', 'campus_life_notes',
        'follow_up_required', 'action_items_student', 'action_items_mentor', 'notify_parent'
    ]
    
    # List of all fields that are 5-star ratings
    rating_fields = [
        'teaching_quality_rating', 'facilities_rating', 'content_relevancy_rating',
        'assessment_rating', 'hostel_rating', 'food_rating', 'transport_rating', 'sports_rating'
    ]
    
    for field in optional_fields:
        if field in kwargs:
            value = kwargs.get(field)
            
            # --- THIS IS THE NEW, SMART LOGIC ---
            # If the field is a rating field and the value is an integer (like 4),
            # convert it to the correct float format (like 0.8).
            if field in rating_fields and isinstance(value, int) and 1 <= value <= 5:
                log_data[field] = value / 5.0
            else:
                # Otherwise, use the value as is.
                log_data[field] = value

    # --- 4. Create and Save the Document ---
    try:
        doc = frappe.get_doc(log_data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return doc.as_dict()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "create_mentorship_log_entry API Error")
        frappe.throw(f"An error occurred while creating the log entry: {e}")

@frappe.whitelist(methods=["PUT"])
def update_mentorship_log_entry(log_id, **kwargs):
    """
    Updates an existing Mentorship Log Entry.
    
    :param log_id: The unique name/ID of the log entry to update.
    :param kwargs: A dictionary of fields and their new values.
    """
    # --- 1. Validate Input ---
    if not log_id:
        frappe.throw("Required parameter 'log_id' is missing.")
    if not kwargs:
        frappe.throw("No data provided to update.")

    try:
        # --- 2. Get the Existing Document ---
        doc = frappe.get_doc("Mentorship Log Entry", log_id)

        # --- 3. Update the Fields with New Data ---
        # List of all fields that are 5-star ratings
        rating_fields = [
            'teaching_quality_rating', 'facilities_rating', 'content_relevancy_rating',
            'assessment_rating', 'hostel_rating', 'food_rating', 'transport_rating', 'sports_rating'
        ]

        # Iterate through the provided data and set the new values
        for field, value in kwargs.items():
            # Check if the field actually exists on the document to avoid errors
            if hasattr(doc, field):
                # Reuse the smart logic to convert integer ratings to floats
                if field in rating_fields and isinstance(value, int) and 1 <= value <= 5:
                    doc.set(field, value / 5.0)
                else:
                    doc.set(field, value)
        
        # --- 4. Save the Document and Commit ---
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        # Return the fully updated document as confirmation
        return doc.as_dict()

    except frappe.DoesNotExistError:
        frappe.throw(f"Mentorship Log Entry with ID '{log_id}' not found.", frappe.NotFound)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "update_mentorship_log_entry API Error")
        frappe.throw(f"An error occurred while updating the log entry: {e}")
