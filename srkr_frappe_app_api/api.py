import frappe
from frappe.utils import get_datetime, get_time_str, get_datetime_str, getdate # get_datetime_str is not strictly needed anymore but get_time is
import re 
# import traceback # Not needed without debug prints
from datetime import timedelta, datetime as dt
import requests
from erpnext.education.doctype.student_attendance_tool.student_attendance_tool import get_student_attendance_percentage

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
        order_by="date asc, name asc"
    )

    if not attendance_records:
        return []

    detailed_attendance = []

    for record in attendance_records:
        # --- CHECK IF COURSE SCHEDULE IS LINKED ---
        if not record.get("course_schedule"):
            # Optional: Log that this record is being skipped
            # frappe.log_message(
            #     title="API: Missing Course Schedule",
            #     message=f"Student Attendance record '{record.name}' for student '{student}' on {record.date.strftime('%Y-%m-%d')} has no Course Schedule linked. Skipping."
            # )
            continue # Skip processing this record and move to the next one
        # --- END OF CHECK ---

        current_record_date_obj = record.date
        current_record_date_str = current_record_date_obj.strftime('%Y-%m-%d')

        # Initialize variables that depend on Course Schedule details
        class_name_val = None
        course_actual_id = None
        calendar_id_val = None
        course_schedule_color_val = None
        start_datetime_formatted = None
        end_datetime_formatted = None

        attendance_status_color = "green" if record.status == "Present" else ("red" if record.status == "Absent" else "orange")

        # Since we passed the check, record.get("course_schedule") is guaranteed to have a value.
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
                    class_name_val = f"Unknown Course ({course_actual_id})"
                except Exception as e_course:
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
                # else: Time objects are not valid timedelta after conversion (start/end will remain None)
            # else: from_time or to_time are missing in Course Schedule (start/end will remain None)

        except frappe.DoesNotExistError:
            class_name_val = f"Course Schedule Missing ({course_schedule_name})" # CS doc itself not found
        except Exception as e_cs:
            class_name_val = f"Error processing CS ({course_schedule_name})"

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

@frappe.whitelist()
def sync_student_results(student_id):
    """
    Fetches exam results for a given student from the external API
    and syncs them into the Semester Result DocType.
    """
    try:
        student_doc = frappe.get_doc("Student", student_id)
        reg_no = student_doc.custom_hall_ticket_number

        if not reg_no:
            frappe.throw(f"Hall Ticket Number (regNo) not found for student {student_doc.student_name}")

        api_key = frappe.conf.get("srkr_api_key")
        if not api_key:
            frappe.throw("SRKR API Key is not set in site_config.json")

        base_url = "https://api.srkrexams.in/api/Result/GetResultByRegNo"
        params = {"regNo": reg_no, "sSEM": "ALL"}
        headers = {"x-api-key": api_key}

        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        api_data = response.json()

        if not api_data.get("success") or not api_data.get("data"):
            frappe.msgprint("API call successful, but no result data was returned.")
            return {"status": "no_data"}

        results = api_data["data"].get("results", [])
        if not results:
            frappe.msgprint("No semester results found for this student.")
            return {"status": "no_data"}

        synced_semesters = 0
        for sem_result in results:
            semester_name = sem_result.get("semester")
            semester_doc_name = frappe.db.get_value("Semester", {"semester_no": semester_name})

            if not semester_doc_name:
                frappe.log_error(f"Semester '{semester_name}' not found in Frappe. Skipping.", "SRKR API Sync")
                continue
            
            existing_result = frappe.db.exists("Semester Result", {"student": student_id, "semester": semester_doc_name})

            doc = frappe.get_doc("Semester Result", existing_result) if existing_result else frappe.new_doc("Semester Result")
            doc.student = student_id
            doc.semester = semester_doc_name
            doc.sgpa = sem_result.get("sgpa")
            doc.cgpa = sem_result.get("cgpa")
            doc.total_credits = sem_result.get("totalCredits")
            doc.credits_secured = sem_result.get("creditsSecured")
            doc.api_url = response.url

            doc.set("subjects", [])
            for subject in sem_result.get("subjects", []):
                course_doc_name = frappe.db.get_value("Course", {"custom_course_code": subject.get("code")})
                doc.append("subjects", {
                    "course": course_doc_name,
                    "subject_code": subject.get("code"),
                    "subject_name": subject.get("name"),
                    "credits": subject.get("credits"),
                    "grade": subject.get("grade"),
                    "result": subject.get("result"),
                    "exam_session": subject.get("exammy"),
                })
            
            doc.save(ignore_permissions=True)
            synced_semesters += 1

        frappe.db.commit()
        frappe.msgprint(f"Successfully synced {synced_semesters} semester(s) of results for {student_doc.student_name}.")
        return {"status": "success"}

    except requests.exceptions.RequestException as e:
        frappe.log_error(frappe.get_traceback(), "SRKR API Sync Error")
        frappe.throw(f"API Connection Error: {e}", title="API Error")
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SRKR API Sync Error")
        frappe.throw(f"An unexpected error occurred: {e}", title="Sync Error")

@frappe.whitelist()
def get_student_academic_summary(student):
    """
    Fetches the academic summary for a given student, including current courses,
    attendance, and historical exam results. This powers the mentor's dashboard.
    """
    if not student:
        return None

    # Find the student's current active program enrollment
    enrollment = frappe.get_all(
        "Program Enrollment",
        filters={"student": student, "docstatus": 1},
        fields=["academic_year", "academic_term", "program"],
        order_by="creation desc",
        limit=1
    )
    
    if not enrollment:
        return {
            "courses": [],
            "results": [],
            "status": "no_enrollment"
        }

    current_term = enrollment[0].academic_term
    current_year = enrollment[0].academic_year
    program = enrollment[0].program

    # 1. Get courses and attendance for the current term
    course_enrollments = frappe.get_all(
        "Course Enrollment",
        filters={"student": student, "academic_term": current_term},
        fields=["course", "course_name"]
    )

    courses_data = []
    for course in course_enrollments:
        try:
            attendance = get_student_attendance_percentage(
                student=student,
                course=course.course,
                academic_year=current_year,
                academic_term=current_term
            )
            courses_data.append({
                "course_code": course.course,
                "course_name": course.course_name,
                "attendance": round(attendance, 2)
            })
        except Exception as e:
            frappe.log_error(
                f"Error fetching attendance for student {student}, course {course.course}: {str(e)}",
                "Mentorship Dashboard Error"
            )
            # If attendance tool fails for a course, record it gracefully
            courses_data.append({
                "course_code": course.course,
                "course_name": course.course_name,
                "attendance": "N/A"
            })
    
    # 2. Get exam results data from our newly implemented feature
    results_data = []
    try:
        # Get all semester results for the student
        semester_results = frappe.get_all(
            "Semester Result",
            filters={"student": student},
            fields=["name", "semester", "sgpa", "cgpa", "total_credits", "credits_secured"],
            order_by="semester desc"
        )
        
        for result in semester_results:
            # For each semester, get the subject results
            subject_data = frappe.get_all(
                "Subject Result",
                filters={"parent": result.name},
                fields=["subject_code", "subject_name", "credits", "grade", "result", "exam_session"]
            )
            
            results_data.append({
                "semester": result.semester,
                "sgpa": result.sgpa,
                "cgpa": result.cgpa,
                "total_credits": result.total_credits,
                "credits_secured": result.credits_secured,
                "subjects": subject_data
            })
    except Exception as e:
        frappe.log_error(
            f"Error fetching exam results for student {student}: {str(e)}",
            "Mentorship Dashboard Error"
        )
        # If there's an error, we'll return an empty results array with an error flag
        results_data = []

    return {
        "student": student,
        "program": program,
        "academic_term": current_term,
        "academic_year": current_year,
        "courses": courses_data,
        "results": results_data,
        "status": "success"
    }
