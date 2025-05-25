import frappe

@frappe.whitelist(allow_guest=True)
def hello_world():
    return "Hello from srkr_frappe_app_api!"

@frappe.whitelist()
def get_student_attendance(student_id):
    """
    Retrieves attendance records for a specific student.
    (Assuming Student and Attendance DocTypes exist and are linked)
    """
    if not student_id:
        frappe.throw("Student ID is required.", title="Missing Parameter")

    # Check if student exists (optional but good practice)
    if not frappe.db.exists("Student", student_id):
        frappe.response.status_code = 404  # Not Found
        return {"error": f"Student with ID '{student_id}' not found."}

    # Placeholder for actual attendance fetching logic
    attendance_records = [
        {"date": "2023-01-01", "status": "Present"},
        {"date": "2023-01-02", "status": "Absent"},
    ]
    return {"student_id": student_id, "attendance": attendance_records}

@frappe.whitelist(allow_guest=True)
def get_student_details(student_id):
    """
    Retrieves details for a specific student based on their ID (name).
    :param student_id: The ID (name) of the student.
    """
    if not student_id:
        frappe.throw("Student ID is required.", title="Missing Parameter")

    # Check if the student document exists
    if not frappe.db.exists("Student", student_id):
        frappe.response.status_code = 404
        return {"error": f"Student with ID '{student_id}' not found."}

    student_fields = ["name", "first_name", "last_name", "email_address", "date_of_birth", "program"]

    try:
        student_doc = frappe.get_doc("Student", student_id)
        student_data = {field: student_doc.get(field) for field in student_fields if hasattr(student_doc, field)}
    except frappe.DoesNotExistError:
        frappe.response.status_code = 404
        return {"error": f"Student with ID '{student_id}' does not exist."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_student_details")
        frappe.response.status_code = 500
        return {"error": "An unexpected error occurred while fetching student details."}

    return student_data

@frappe.whitelist(allow_guest=True)
def get_user_details(email_id):
    """
    Retrieves details for a specific Frappe User based on their email ID (name).
    :param email_id: The email ID (name) of the Frappe User.
    """
    if not email_id:
        frappe.throw("User Email ID is required.", title="Missing Parameter")

    if not frappe.db.exists("User", email_id):
        frappe.response.status_code = 404
        return {"error": f"User with Email ID '{email_id}' not found."}

    user_fields_to_fetch = ["name", "first_name", "last_name", "full_name", "email", "enabled", "user_type"]

    try:
        user_doc = frappe.get_doc("User", email_id)
        user_data = {field: user_doc.get(field) for field in user_fields_to_fetch if hasattr(user_doc, field)}
    except frappe.DoesNotExistError:
        frappe.response.status_code = 404
        return {"error": f"User with Email ID '{email_id}' does not exist."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_user_details")
        frappe.response.status_code = 500
        return {"error": "An unexpected error occurred while fetching user details."}

    return user_data