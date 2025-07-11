# srkr_frappe_app_api/srkr_frappe_app_api/instructor/schedule_api.py

import frappe
from frappe.utils import getdate, get_time # Import get_time if it was missed previously
import re 
from datetime import timedelta, datetime as dt

@frappe.whitelist(allow_guest=True)
def get_instructor_schedule(instructor, start_date, end_date=None):
    if not instructor or not start_date:
        frappe.throw("Instructor ID and Start Date are required.")

    # --- Date Validation and Formatting (Unchanged) ---
    try:
        parsed_start_date_obj = getdate(start_date)
        start_date_str = parsed_start_date_obj.strftime('%Y-%m-%d')
    except Exception as e:
        frappe.throw(f"Error processing Start Date: {e}")

    if end_date:
        try:
            parsed_end_date_obj = getdate(end_date)
            end_date_str = parsed_end_date_obj.strftime('%Y-%m-%d')
        except Exception as e:
            frappe.throw(f"Error processing End Date: {e}")
    else:
        end_date_str = start_date_str

    if getdate(start_date_str) > getdate(end_date_str):
        frappe.throw("Start Date cannot be after End Date.")
    # --- (End of Date validation) ---

    # --- CORE MODIFICATION: Use frappe.db.sql with a JOIN ---
    # We join with 'tabRoom' to fetch the room_name directly in one query.
    # We use table aliases (CS for Course Schedule, R for Room) for clarity.
    q = """
        SELECT
            CS.`name`,
            CS.`schedule_date`,
            CS.`course`,
            CS.`from_time`,
            CS.`to_time`,
            CS.`room`,
            R.`room_name`, -- <<< CHANGE: Fetched the room_name
            CS.`student_group`,
            CS.`color`,
            CS.`class_schedule_color`,
            CS.`instructor`,
            CS.`co_instructor_1`,
            CS.`co_instructor_2`
        FROM
            `tabCourse Schedule` AS CS
        LEFT JOIN `tabRoom` AS R ON CS.room = R.name -- <<< CHANGE: Joined with the Room table
        WHERE
            (CS.`instructor` = %(instructor)s OR
             CS.`co_instructor_1` = %(instructor)s OR
             CS.`co_instructor_2` = %(instructor)s)
            AND
            CS.`schedule_date` BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY
            CS.`schedule_date` asc, CS.`from_time` asc
    """
    
    course_schedules = frappe.db.sql(q, values={
        "instructor": instructor,
        "start_date": start_date_str,
        "end_date": end_date_str
    }, as_dict=True)
    # --- END OF CORE MODIFICATION ---

    if not course_schedules:
        return []

    detailed_schedule = []

    for cs_record in course_schedules:
        # The rest of your processing logic is preserved below
        course_name_val = None
        course_actual_id = None
        calendar_id_val = None
        start_datetime_formatted = None
        end_datetime_formatted = None

        # --- Attendance Summary Handling (Unchanged) ---
        attendance_summary = {}
        if cs_record.name:
            student_attendance_for_cs = frappe.get_all(
                "Student Attendance",
                filters={
                    "course_schedule": cs_record.name,
                    "docstatus": 1
                },
                fields=["status"]
            )

            if student_attendance_for_cs:
                attendance_summary["total_students"] = len(student_attendance_for_cs)
                attendance_summary["present_count"] = 0
                attendance_summary["absent_count"] = 0
                attendance_summary["on_leave_count"] = 0

                for att_entry in student_attendance_for_cs:
                    if att_entry.status == "Present":
                        attendance_summary["present_count"] += 1
                    elif att_entry.status == "Absent":
                        attendance_summary["absent_count"] += 1
                    elif att_entry.status == "On Leave":
                        attendance_summary["on_leave_count"] += 1

        # --- Course Name Handling (Unchanged) ---
        if cs_record.course:
            course_actual_id = cs_record.course
            try:
                course_doc = frappe.get_doc("Course", course_actual_id)
                course_name_val = course_doc.course_name
                temp_id = str(course_actual_id).lower().strip()
                calendar_id_val = re.sub(r'\s+', '_', temp_id)
            except frappe.DoesNotExistError:
                course_name_val = f"Unknown Course ({course_actual_id})"
                temp_id = str(course_actual_id).lower().strip()
                calendar_id_val = re.sub(r'\s+', '_', temp_id)
            except Exception:
                course_name_val = f"Error fetching course ({course_actual_id})"
                temp_id = str(course_actual_id).lower().strip()
                calendar_id_val = re.sub(r'\s+', '_', temp_id)
        else:
            course_name_val = "Course Not Specified"

        # --- Datetime Formatting (Unchanged) ---
        from_time_obj = cs_record.from_time
        to_time_obj = cs_record.to_time
        schedule_date_obj = cs_record.schedule_date

        if from_time_obj and to_time_obj and schedule_date_obj:
            if isinstance(from_time_obj, str):
                from_time_obj = frappe.utils.get_time(from_time_obj)
            if isinstance(to_time_obj, str):
                to_time_obj = frappe.utils.get_time(to_time_obj)

            if isinstance(from_time_obj, timedelta) and isinstance(to_time_obj, timedelta):
                from_hours = from_time_obj.seconds // 3600
                from_minutes = (from_time_obj.seconds // 60) % 60
                to_hours = to_time_obj.seconds // 3600
                to_minutes = (to_time_obj.seconds // 60) % 60
                
                start_dt_obj = dt.combine(schedule_date_obj, dt.min.time()).replace(hour=from_hours, minute=from_minutes)
                end_dt_obj = dt.combine(schedule_date_obj, dt.min.time()).replace(hour=to_hours, minute=to_minutes)
                
                start_datetime_formatted = start_dt_obj.strftime('%Y-%m-%d %H:%M')
                end_datetime_formatted = end_dt_obj.strftime('%Y-%m-%d %H:%M')
        
        schedule_color = cs_record.get("color") or cs_record.get("class_schedule_color")

        # --- MODIFICATION: Updated the final output dictionary ---
        entry = {
            "course_schedule_id": cs_record.name,
            "date": cs_record.schedule_date.strftime('%Y-%m-%d'),
            "course_name": course_name_val,
            "course_id": course_actual_id,
            "calendar_id": calendar_id_val,
            "start_time": start_datetime_formatted,
            "end_time": end_datetime_formatted,
            "room_id": cs_record.get("room"),         # <<< CHANGE: Renamed 'room' to 'room_id' for clarity
            "room_name": cs_record.get("room_name"),  # <<< CHANGE: Added the new 'room_name' field
            "student_group": cs_record.get("student_group"),
            "color": schedule_color,
            "attendance_summary": attendance_summary,
            "instructor": cs_record.instructor,
            "co_instructor_1": cs_record.co_instructor_1,
            "co_instructor_2": cs_record.co_instructor_2
        }
        detailed_schedule.append(entry)

    return detailed_schedule

@frappe.whitelist()
def get_instructor_info():
    """
    Fetches information for the currently logged-in user if they are linked to an Employee record.
    Also fetches instructor name from Instructor doctype if linked.
    Returns specific fields including an 'instructor_id' and 'instructor_name'.
    """
    current_user_email = frappe.session.user

    if current_user_email == "Administrator":
        return {"message": "Administrator account selected. No specific instructor profile to display."}

    employee_doc_name = None # To store the name/ID of the employee document

    # Method 1: Check if User doc is directly linked to an Employee
    user_doc = frappe.get_doc("User", current_user_email)
    print(f"User document fetched for {current_user_email}: {user_doc.name}, Employee: {user_doc.get('employee')}")
    if user_doc.get("employee"):
        employee_doc_name = user_doc.employee
    
    # Method 2: If not directly linked, try to find Employee by email matching fields
    if not employee_doc_name:
        email_match_fields = ["user_id", "company_email", "personal_email"] 
        for field_name in email_match_fields:
            employee_found = frappe.get_all(
                "Employee",
                filters={field_name: current_user_email},
                fields=["name"],
                limit=1
            )
            if employee_found:
                employee_doc_name = employee_found[0].name
                break
    
    if employee_doc_name:
        try:
            employee_doc = frappe.get_doc("Employee", employee_doc_name)
            
            # Base instructor info from Employee doctype
            instructor_info = {
                "instructor_id": employee_doc.name,
                "employee_name": employee_doc.get("employee_name"),
                "first_name": employee_doc.get("first_name"),
                "last_name": employee_doc.get("last_name"),
                "gender": employee_doc.get("gender"),
                "date_of_birth": employee_doc.get("date_of_birth"),
                "company_email": employee_doc.get("company_email"),
                "department": employee_doc.get("department"),
                "designation": employee_doc.get("designation"),
                "image": employee_doc.get("image"),
            }
            
            # Try to fetch instructor name from Instructor doctype using employee field
            instructor_found = frappe.get_all(
                "Instructor",
                filters={"employee": employee_doc_name},  # Link using employee field
                fields=["instructor_name", "name"],  # Get both instructor_name and instructor ID
                limit=1
            )
            
            if instructor_found:
                instructor_info["instructor_name"] = instructor_found[0].instructor_name
                instructor_info["instructor_record_id"] = instructor_found[0].name  # Optional: include instructor record ID
                print(f"Found instructor name: {instructor_found[0].instructor_name} with ID: {instructor_found[0].name}")
            else:
                instructor_info["instructor_name"] = None
                instructor_info["instructor_record_id"] = None
                print(f"No instructor record found for employee: {employee_doc_name}")

            return instructor_info
            
        except frappe.DoesNotExistError:
            return {"error": f"Employee record {employee_doc_name} could not be fully loaded."}
        except Exception as e:
            return {"error": f"An error occurred: {str(e)}"}
    else:
        return {"message": f"No Employee record found linked to user {current_user_email}."}
    """
    Fetches information for the currently logged-in user if they are linked to an Employee record.
    Also fetches instructor name from Instructor doctype if linked.
    Returns specific fields including an 'instructor_id' and 'instructor_name'.
    """
    current_user_email = frappe.session.user

    if current_user_email == "Administrator":
        return {"message": "Administrator account selected. No specific instructor profile to display."}

    employee_doc_name = None # To store the name/ID of the employee document

    # Method 1: Check if User doc is directly linked to an Employee
    user_doc = frappe.get_doc("User", current_user_email)
    print(f"User document fetched for {current_user_email}: {user_doc.name}, Employee: {user_doc.get('employee')}")
    if user_doc.get("employee"):
        employee_doc_name = user_doc.employee
    
    # Method 2: If not directly linked, try to find Employee by email matching fields
    if not employee_doc_name:
        email_match_fields = ["user_id", "company_email", "personal_email"] 
        for field_name in email_match_fields:
            employee_found = frappe.get_all(
                "Employee",
                filters={field_name: current_user_email},
                fields=["name"],
                limit=1
            )
            if employee_found:
                employee_doc_name = employee_found[0].name
                break
    
    if employee_doc_name:
        try:
            employee_doc = frappe.get_doc("Employee", employee_doc_name)
            print(f"Employee document fetched for {employee_doc_name}: {employee_doc.get('ID')}")
            print(f"Employee document fields: {employee_doc.as_dict()}")
            
            # Base instructor info from Employee doctype
            instructor_info = {
                "instructor_id": employee_doc.name,
                "employee_name": employee_doc.get("employee_name"),
                "first_name": employee_doc.get("first_name"),
                "last_name": employee_doc.get("last_name"),
                "gender": employee_doc.get("gender"),
                "date_of_birth": employee_doc.get("date_of_birth"),
                "company_email": employee_doc.get("company_email"),
                "department": employee_doc.get("department"),
                "designation": employee_doc.get("designation"),
                "image": employee_doc.get("image"),
            }
            
            # Try to fetch instructor name from Instructor doctype
            # Method 1: Look for Instructor record linked by employee ID
            instructor_found = frappe.get_all(
                "Instructor",
                filters={"name": employee_doc_name},  # Assuming instructor ID matches employee ID
                fields=["instructor_name"],
                limit=1
            )
            
            if instructor_found:
                instructor_info["instructor_name"] = instructor_found[0].instructor_name
                print(f"Found instructor name: {instructor_found[0].instructor_name}")
            else:
                # Method 2: Try matching by employee name if direct ID match fails
                employee_name = employee_doc.get("employee_name")
                if employee_name:
                    instructor_by_name = frappe.get_all(
                        "Instructor",
                        filters={"instructor_name": employee_name},
                        fields=["instructor_name"],
                        limit=1
                    )
                    if instructor_by_name:
                        instructor_info["instructor_name"] = instructor_by_name[0].instructor_name
                        print(f"Found instructor name by employee name match: {instructor_by_name[0].instructor_name}")
                    else:
                        instructor_info["instructor_name"] = None
                        print("No matching instructor record found")
                else:
                    instructor_info["instructor_name"] = None
                    print("No employee name available for instructor lookup")

            return instructor_info
            
        except frappe.DoesNotExistError:
            return {"error": f"Employee record {employee_doc_name} could not be fully loaded."}
        except Exception as e:
            return {"error": f"An error occurred: {str(e)}"}
    else:
        return {"message": f"No Employee record found linked to user {current_user_email}."}