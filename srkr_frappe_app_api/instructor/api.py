# srkr_frappe_app_api/srkr_frappe_app_api/instructor/api.py

import frappe
from frappe.utils import getdate, get_time, today # <-- Added 'today'
import re 
from datetime import timedelta, datetime as dt
import json
from frappe import _
import requests  # <-- Added
from urllib.parse import urlencode # <-- Added

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


@frappe.whitelist()
def mark_attendances(
    students_present, students_absent, course_schedule=None, student_group=None, date=None, taught_topics=None
):
    """
    Creates Multiple Attendance Records and saves the topics taught for each course schedule.
    """
    if student_group:
        academic_year = frappe.db.get_value("Student Group", student_group, "academic_year")
        if academic_year:
            year_start_date, year_end_date = frappe.db.get_value(
                "Academic Year", academic_year, ["year_start_date", "year_end_date"]
            )
            if getdate(date) < getdate(year_start_date) or getdate(date) > getdate(year_end_date):
                frappe.throw(
                    _("Attendance cannot be marked outside of Academic Year {0}").format(academic_year)
                )

    present = json.loads(students_present)
    absent = json.loads(students_absent)

    topics_object_list = []
    if taught_topics:
        try:
            topics_object_list = json.loads(taught_topics)
            if not isinstance(topics_object_list, list):
                topics_object_list = []
        except Exception:
            topics_object_list = []

    course_schedules = []
    if course_schedule:
        if isinstance(course_schedule, str):
            try:
                course_schedules = json.loads(course_schedule)
            except Exception:
                course_schedules = [s.strip() for s in course_schedule.split(",") if s.strip()]
        else:
             course_schedules = course_schedule

    if not isinstance(course_schedules, list):
        course_schedules = [course_schedules]

    for cs_id in course_schedules:
        for d in present:
            make_attendance_records(d["student"], d["student_name"], "Present", cs_id, student_group, date)
        for d in absent:
            make_attendance_records(d["student"], d["student_name"], "Absent", cs_id, student_group, date)

        if cs_id and topics_object_list:
            try:
                schedule_doc = frappe.get_doc("Course Schedule", cs_id)
                
                # ***** THE FIX IS HERE *****
                # The field name MUST match what is in the DocType. If added via Customize Form,
                # it is prefixed with 'custom_'. Your getdoc response confirmed this.
                child_table_fieldname = "custom_taught_topics" 

                schedule_doc.set(child_table_fieldname, [])
                for topic_obj in topics_object_list:
                    if not topic_obj.get("topic"):
                        continue
                    schedule_doc.append(child_table_fieldname, {
                        "topic": topic_obj.get("topic"),
                        "completed": 1 if topic_obj.get("completed") else 0
                    })
                schedule_doc.save(ignore_permissions=True)
            except frappe.DoesNotExistError:
                frappe.log_error(f"Course Schedule {cs_id} not found when saving topics.", "Mark Attendance API")
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Error saving taught topics for {cs_id}")

    frappe.db.commit()
    frappe.msgprint(_("Attendance and Taught Topics have been saved successfully."))

def make_attendance_records(
	student, student_name, status, course_schedule=None, student_group=None, date=None
):
	"""Creates/Update Attendance Record.

	:param student: Student.
	:param student_name: Student Name.
	:param course_schedule: Course Schedule.
	:param status: Status (Present/Absent/Leave).
	"""
	student_attendance = frappe.get_doc(
		{
			"doctype": "Student Attendance",
			"student": student,
			"course_schedule": course_schedule,
			"student_group": student_group,
			"date": date,
		}
	)
	if not student_attendance:
		student_attendance = frappe.new_doc("Student Attendance")
	student_attendance.student = student
	student_attendance.student_name = student_name
	student_attendance.course_schedule = course_schedule
	student_attendance.student_group = student_group
	student_attendance.date = date
	student_attendance.status = status
	student_attendance.save()
	student_attendance.submit()

# ------------------------------------------------------------------
# --- CONSOLIDATED SMS FUNCTIONS (STUDENTS AND INSTRUCTORS) ---
# ------------------------------------------------------------------

def send_summary_sms_helper(mobile_no, message_text, template_id):
    """Generic helper function to call the SMS API."""
    API_URL = "https://smslogin.co/v3/api.php"
    API_KEY = "441580e5effd27db3eaa"
    USERNAME = "srkrec"
    SENDER_ID = "SRKREC"
    
    params = {"username": USERNAME, "apikey": API_KEY, "senderid": SENDER_ID, "mobile": mobile_no, "message": message_text, "templateid": template_id}
    
    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        response_text = response.text
        campid = response_text.split("'")[3] if 'campid' in response_text else response_text
        print(f"SMS API Success for {mobile_no}. Response: {response.text}")
        return campid
    except Exception as e:
        print(f"SMS API Failed for {mobile_no}. Error: {e}")
        frappe.log_error(frappe.get_traceback(), title=f"SMS API Call Failed for {mobile_no}")
        return None

@frappe.whitelist()
def send_daily_attendance_summary():
    """Scheduled function to send a consolidated SMS to parents of absent students."""
    processing_date = today()
    print(f"--- Running Daily Student Attendance Summary for {processing_date} ---")

    # Use the existing "SMS Log" and filter by the "sent_to" convention
    logs_today = frappe.get_all("SMS Log", filters={"sent_on": processing_date}, pluck="sent_to")
    already_processed = [log.split(": ")[1] for log in logs_today if log and log.startswith("Student: ")]
    print(f"Students already processed today: {already_processed}")

    # --- LOGIC RESTORED: Get a unique list of students who were marked absent at least once today. ---
    absent_students = frappe.get_all(
        "Student Attendance",
        filters={"date": processing_date, "status": "Absent"},
        fields=["DISTINCT student"],
        pluck="student"
    )
    print(f"Found {len(absent_students)} absent students today: {absent_students}")

    for student_id in absent_students:
        if student_id in already_processed:
            print(f"Skipping student {student_id}, summary already sent.")
            continue
        try:
            print(f"\n--- Processing Student: {student_id} ---")
            student_group = frappe.get_value("Student Attendance", {"student": student_id, "date": processing_date}, "student_group")

            # --- START: Temporary ECE Filter ---
            # This condition will be removed after testing is complete.
            if not student_group or not ("ECE" in student_group and ("AY2526-SEM-03-A" in student_group)):
                print(f"Skipping student {student_id} from group '{student_group}' as it does not match ECE AY2526-SEM-03-A criteria.")
                continue
            student_doc = frappe.get_doc("Student", student_id)
            mobile_no, reg_no = student_doc.get("custom_father_mobile_number"), student_doc.get("custom_student_id")
            if not mobile_no: print(f"Warning: No mobile number for student {student_id}. Skipping."); continue
            if not mobile_no.startswith("91"): mobile_no = "91" + mobile_no
            
            attended_count = frappe.db.count("Student Attendance", {"student": student_id, "date": processing_date, "status": "Present"})
            total_classes = frappe.db.count("Student Attendance", {"student": student_id, "date": processing_date})
            
            print(f"Summary for {student_id}: Attended={attended_count}, Total (recorded)={total_classes}")
            
            ward_variable = f"({reg_no or student_id})"
            date_variable = getdate(processing_date).strftime('%d-%m-%Y')
            attd_con_variable = f"({attended_count}/{total_classes})"
            message_text = f"Dear Parent, Your ward {ward_variable} is absent on {date_variable} . Please take care. (Attd/Con):{attd_con_variable} -Principal, SRKREC"
            print(f"Constructed Message: {message_text}")
            
            # UNCOMMENT to send SMS
            message_id = send_summary_sms_helper(mobile_no, message_text, "1707163646397399883")
            # message_id = "STUDENT_SMS_DISABLED"
            
            if message_id:
                log_doc = frappe.new_doc("SMS Log")
                log_doc.sent_on = processing_date
                log_doc.message = message_text
                log_doc.requested_numbers = mobile_no
                log_doc.sent_to = f"Student: {student_id}" # Using the convention
                log_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"Successfully logged summary for student {student_id}.")
        except Exception as e:
            print(f"!!! ERROR for student {student_id}: {e}"); frappe.log_error(frappe.get_traceback(), f"Summary failed for student {student_id}"); frappe.db.rollback()
    print("--- Daily Student Attendance Summary complete. ---")

# In your api.py file, replace the old/duplicated version of this function with this new one.

# In your api.py file, replace the old/duplicated version of this function with this new one.

@frappe.whitelist()
def send_instructor_attendance_reminders():
    """
    Scheduled function to find instructors with missed attendance and send a reminder.
    (Optimized Logic)
    """
    processing_date = today()
    print(f"--- Running Instructor Attendance Reminder for {processing_date} ---")

    # Use the existing "SMS Log" and filter by the "sent_to" convention
    logs_today = frappe.get_all("SMS Log", filters={"sent_on": processing_date}, pluck="sent_to")
    already_reminded = [log.split(": ")[1] for log in logs_today if log and log.startswith("Instructor: ")]
    print(f"Instructors already reminded today: {already_reminded}")

    # 1. Get all classes scheduled for today and group them by instructor.
    scheduled_classes_by_instructor = {}
    all_scheduled_classes = frappe.get_all("Course Schedule", filters={"schedule_date": processing_date}, fields=["name", "instructor"])
    
    if not all_scheduled_classes:
        print("No classes were scheduled for today. Exiting.")
        return

    for schedule in all_scheduled_classes:
        instructor_id = schedule.get("instructor")
        if instructor_id:
            # setdefault ensures the key exists before adding to the set
            scheduled_classes_by_instructor.setdefault(instructor_id, set()).add(schedule.name)
    
    # 2. Get the set of all class schedules where attendance WAS taken today.
    taken_attendance_ids = set(frappe.get_all(
        "Student Attendance",
        filters={"date": processing_date},
        fields=["DISTINCT course_schedule"],
        pluck="course_schedule"
    ))
    
    # 3. Loop through each instructor and find their pending classes.
    for instructor_id, their_scheduled_ids in scheduled_classes_by_instructor.items():
        if instructor_id in already_reminded:
            print(f"Skipping instructor {instructor_id}, already reminded."); continue

        # Find the difference: which of this instructor's classes are NOT in the "taken" set.
        pending_ids = their_scheduled_ids - taken_attendance_ids
        pending_count = len(pending_ids)

        # If the instructor has pending classes, proceed to notify them.
        if pending_count > 0:
            try:
                print(f"\n--- Processing Instructor: {instructor_id} with {pending_count} pending classes ---")
                instructor_doc = frappe.get_doc("Instructor", instructor_id)
                employee_id = instructor_doc.employee
                if not employee_id: print(f"Warning: Instructor {instructor_id} not linked to an Employee."); continue
                
                mobile_no = frappe.get_value("Employee", employee_id, "cell_number")
                if not mobile_no: print(f"Warning: Employee {employee_id} has no mobile number."); continue
                if not mobile_no.startswith("91"): mobile_no = "91" + mobile_no
                
                var1 = instructor_doc.instructor_name
                var2 = f"for {getdate(processing_date).strftime('%d-%m-%Y')}"
                message_text = f"Dear {var1}, SRKREC Reminder: You have pending attendance(s) {var2}. Please update the portal at your earliest convenience. - SRKREC"
                print(f"Constructed Message: {message_text}")
                
                # UNCOMMENT to send SMS
                # message_id = send_summary_sms_helper(mobile_no, message_text, "1707175947082321519")
                message_id = "INSTRUCTOR_SMS_DISABLED"
                
                if message_id:
                    log_doc = frappe.new_doc("SMS Log")
                    log_doc.sent_on = processing_date
                    log_doc.message = message_text
                    log_doc.requested_numbers = mobile_no
                    log_doc.sent_to = f"Instructor: {instructor_id}"
                    log_doc.insert(ignore_permissions=True)
                    frappe.db.commit()
                    print(f"Successfully logged reminder for instructor {instructor_id}.")
            except Exception as e:
                print(f"!!! ERROR for instructor {instructor_id}: {e}"); frappe.log_error(frappe.get_traceback(), f"Reminder failed for instructor {instructor_id}"); frappe.db.rollback()

    print("--- Instructor Attendance Reminder complete. ---")  