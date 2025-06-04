import frappe
from frappe.utils import get_datetime, get_time_str, get_datetime_str, getdate # get_datetime_str is not strictly needed anymore but get_time is
import re 
# import traceback # Not needed without debug prints
from datetime import timedelta, datetime as dt

@frappe.whitelist(allow_guest=True)
def hello_world():
    return "Hello from my_student_api!"

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
        frappe.response.status_code = 404 # Not Found
        return {"error": f"Student with ID '{student_id}' not found."}

    # Placeholder for actual attendance fetching logic
    # Example:
    # attendance_records = frappe.get_all(
    # "Attendance",
    # filters={"student": student_id},
    # fields=["date", "status", "subject"] # Customize fields
    # )
    # if not attendance_records:
    # return {"message": f"No attendance records found for student '{student_id}'."}
    # return attendance_records

    # Dummy data for now, replace with actual frappe.get_all call
    attendance_records = [
        {"date": "2023-01-01", "status": "Present"},
        {"date": "2023-01-02", "status": "Absent"},
    ]
    return {"student_id": student_id, "attendance": attendance_records}


@frappe.whitelist(allow_guest=True) # This makes the function accessible via API
def get_student_details(student_id):
    """
    Retrieves details for a specific student based on their ID (name).
    :param student_id: The ID (name) of the student.
    """
    if not student_id:
        frappe.throw("Student ID is required.", title="Missing Parameter")
        return # Should not be reached if frappe.throw is used

    # Check if the student document exists
    if not frappe.db.exists("Student", student_id):
        # Set HTTP status code for "Not Found"
        frappe.response.status_code = 404
        return {"error": f"Student with ID '{student_id}' not found."}

    # Fetch the student document
    # Specify the fields you want to return
    # Ensure these fields exist in your "Student" DocType
    student_fields = ["name", "first_name", "last_name", "email_address", "date_of_birth", "program"] # Customize as needed

    try:
        student_doc = frappe.get_doc("Student", student_id)
        student_data = {field: student_doc.get(field) for field in student_fields if hasattr(student_doc, field)}

        # If you prefer to fetch specific fields directly without loading the whole document (more efficient for few fields):
        # student_data = frappe.get_value("Student", student_id, student_fields, as_dict=True)
        # if not student_data: # frappe.get_value returns None if not found, though frappe.db.exists should catch this
        #     frappe.response.status_code = 404
        #     return {"error": f"Student with ID '{student_id}' not found (get_value check)."}

    except frappe.DoesNotExistError:
        # This case should ideally be caught by frappe.db.exists, but good to have as a fallback
        frappe.response.status_code = 404
        return {"error": f"Student with ID '{student_id}' does not exist."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_student_details")
        frappe.response.status_code = 500 # Internal Server Error
        return {"error": "An unexpected error occurred while fetching student details."}

    return student_data


@frappe.whitelist(allow_guest=True) # NO allow_guest=True - User data can be sensitive
def get_user_details(email_id): # Changed parameter name for clarity
    """
    Retrieves details for a specific Frappe User based on their email ID (name).
    :param email_id: The email ID (name) of the Frappe User.
    """
    if not email_id:
        frappe.throw("User Email ID is required.", title="Missing Parameter")
        return

    # The 'User' DocType's 'name' field is the email address.
    # frappe.db.exists checks if a document with that name exists.
    if not frappe.db.exists("User", email_id):
        frappe.response.status_code = 404 # Not Found
        return {"error": f"User with Email ID '{email_id}' not found."}

    # Specify the fields you want to return from the "User" DocType
    # Common User fields: name, first_name, last_name, email, enabled, user_type, roles
    user_fields_to_fetch = ["name", "first_name", "last_name", "full_name", "email", "enabled", "user_type"] # Customize as needed

    try:
        # Fetch the user document using frappe.get_doc
        user_doc = frappe.get_doc("User", email_id)

        # Construct a dictionary with the requested fields
        user_data = {field: user_doc.get(field) for field in user_fields_to_fetch if hasattr(user_doc, field)}

        # You can also fetch roles if needed:
        # roles = frappe.get_roles(email_id)
        # user_data["roles"] = roles

    except frappe.DoesNotExistError:
        # This case should ideally be caught by frappe.db.exists, but good as a fallback
        frappe.response.status_code = 404
        return {"error": f"User with Email ID '{email_id}' does not exist (get_doc check)."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in get_user_details")
        frappe.response.status_code = 500 # Internal Server Error
        return {"error": "An unexpected error occurred while fetching user details."}

    return user_data

@frappe.whitelist()
def get_student_daily_class_attendance(student, start_date, end_date=None):
    if not student or not start_date:
        frappe.throw("Student ID and Start Date are required.")

    # --- Date Validation and Formatting ---
    try:
        parsed_start_date_obj = getdate(start_date)
        start_date_str = parsed_start_date_obj.strftime('%Y-%m-%d')
    except ValueError:
        frappe.throw(f"Invalid Start Date format provided: '{start_date}'. Please use YYYY-MM-DD.")
    except Exception as e:
        frappe.throw(f"Error processing Start Date: {e}")

    if end_date:
        try:
            parsed_end_date_obj = getdate(end_date)
            end_date_str = parsed_end_date_obj.strftime('%Y-%m-%d')
        except ValueError:
            frappe.throw(f"Invalid End Date format provided: '{end_date}'. Please use YYYY-MM-DD.")
        except Exception as e:
            frappe.throw(f"Error processing End Date: {e}")
    else:
        end_date_str = start_date_str

    if getdate(start_date_str) > getdate(end_date_str):
        frappe.throw("Start Date cannot be after End Date.")
    # --- (End of Date validation) ---

    attendance_filters = [
        ["student", "=", student],
        ["date", "between", [start_date_str, end_date_str]],
        ["docstatus", "=", 1] # Assuming submitted attendance
    ]
    
    student_attendance_fields = ["name", "status", "course_schedule", "date"]
    
    attendance_records = frappe.get_all(
        "Student Attendance",
        filters=attendance_filters,
        fields=student_attendance_fields,
        order_by="date asc, name asc" # Optional: order results
    )

    if not attendance_records:
        return [] 

    detailed_attendance = []

    for record in attendance_records:
        current_record_date_obj = record.date 
        current_record_date_str = current_record_date_obj.strftime('%Y-%m-%d')

        class_name_val = None
        course_actual_id = None
        calendar_id_val = None
        course_schedule_color_val = None
        start_datetime_formatted = None 
        end_datetime_formatted = None   
        
        attendance_status_color = "green" if record.status == "Present" else ("red" if record.status == "Absent" else "orange")

        if record.get("course_schedule"):
            course_schedule_name = record.get("course_schedule")
            try:
                course_schedule_details = frappe.get_doc("Course Schedule", course_schedule_name)
                
                course_schedule_color_val = course_schedule_details.get("color") or course_schedule_details.get("class_schedule_color")

                if course_schedule_details.course:
                    course_actual_id = course_schedule_details.course 
                    try:
                        course_doc = frappe.get_doc("Course", course_actual_id)
                        class_name_val = course_doc.course_name
                        
                        if course_actual_id: 
                            temp_id = str(course_actual_id).lower().strip() 
                            calendar_id_val = re.sub(r'\s+', '_', temp_id)
                        
                    except frappe.DoesNotExistError:
                        # You might want to log this error for monitoring
                        # frappe.log_error(message=f"Course Doc NOT FOUND: {course_actual_id} for CS {course_schedule_name}", title="API Get Student Attendance")
                        class_name_val = f"Unknown Course ({course_actual_id})"
                    except Exception as e_course:
                        # frappe.log_error(message=f"ERROR fetching/processing Course Doc '{course_actual_id}': {e_course}", title="API Get Student Attendance")
                        class_name_val = f"Error fetching course ({course_actual_id})"
                else:
                    class_name_val = "Course Not Specified in Schedule"

                from_time_obj = course_schedule_details.from_time
                to_time_obj = course_schedule_details.to_time

                if from_time_obj and to_time_obj:
                    if isinstance(from_time_obj, str):
                        from_time_obj = frappe.utils.get_time(from_time_obj) 
                    if isinstance(to_time_obj, str):
                        to_time_obj = frappe.utils.get_time(to_time_obj)

                    if isinstance(from_time_obj, timedelta) and isinstance(to_time_obj, timedelta):
                        from_hours = from_time_obj.seconds // 3600
                        from_minutes = (from_time_obj.seconds // 60) % 60
                        
                        to_hours = to_time_obj.seconds // 3600
                        to_minutes = (to_time_obj.seconds // 60) % 60

                        start_dt_obj = dt.combine(current_record_date_obj, dt.min.time()).replace(hour=from_hours, minute=from_minutes)
                        end_dt_obj = dt.combine(current_record_date_obj, dt.min.time()).replace(hour=to_hours, minute=to_minutes)
                        
                        start_datetime_formatted = start_dt_obj.strftime('%Y-%m-%d %H:%M')
                        end_datetime_formatted = end_dt_obj.strftime('%Y-%m-%d %H:%M')
                    # else: You might want to log if time objects are not valid timedelta after conversion
                # else: You might want to log if from_time or to_time are missing in Course Schedule
            
            except frappe.DoesNotExistError:
                # frappe.log_error(message=f"CS Doc NOT FOUND: {course_schedule_name} for SA {record.name}", title="API Get Student Attendance")
                class_name_val = f"Course Schedule Missing ({course_schedule_name})"
            except Exception as e_cs: 
                # frappe.log_error(message=f"GENERIC ERROR processing CS Doc '{course_schedule_name}': {e_cs}", title="API Get Student Attendance")
                class_name_val = f"Error processing CS ({course_schedule_name})"
        # else: Student Attendance record has no Course Schedule link.

        entry = {
            "date": current_record_date_str, 
            "status": record.status,
            "attendance_record_name": record.name,
            "title": class_name_val,
            "calendar_id": calendar_id_val,
            "start": start_datetime_formatted, 
            "end": end_datetime_formatted,   
            "attendance_status_color": attendance_status_color,
            "course_schedule_color": course_schedule_color_val
        }
        detailed_attendance.append(entry)

    return detailed_attendance

