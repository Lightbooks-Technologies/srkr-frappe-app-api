# srkr_frappe_app_api/srkr_frappe_app_api/instructor/api.py

import frappe
from frappe.utils import getdate, get_time, today, now_datetime # <-- Added 'today'
import re 
from datetime import timedelta, datetime as dt
import json
from frappe import _
import requests  # <-- Added
from urllib.parse import urlencode # <-- Added
from datetime import time, timedelta, datetime

# NOTE: Update this date at the beginning of each semester. - YYYY-MM-DD
SEMESTER_START_DATE = '2024-02-12' 

# NOTE: Add SUBSTRINGS of the Student Groups you want to send summaries to.
# This is now a pattern match, not an exact match.
TARGET_STUDENT_GROUP_PATTERNS_FOR_SUMMARIES = [
    'BTECH-SEM-03',
    'BTECH-SEM-05'
]

# NOTE: For instructor reminders, only send notifications for missed attendance
# that matches one of the following patterns. E.g., ['SEM-01'] for first semester.
ACTIVE_STUDENT_GROUP_PATTERNS_FOR_REMINDERS = [
    'SEM-01', 'SEM-04', 'SEM-06'
]

# NOTE: For Daily Attendance Summary, only send SMS to students in groups matching ALL these patterns.
# Example: ["BTECH", "SEM-01"] means the group name must contain BOTH "BTECH" and "SEM-01".
# Leave empty to disable filtering (send to all).
DAILY_SUMMARY_REQUIRED_PATTERNS = ["BTECH", "SEM-01", "SEM-04", "SEM-06"]

# NOTE: Get these Template IDs from your SMS provider.
WEEKLY_ATTENDANCE_SUMMARY_TEMPLATE = '1707163646397399999' # Replace with actual ID
CUMULATIVE_ATTENDANCE_SUMMARY_TEMPLATE = '1707163646397399888' # Replace with actual ID

DAILY_STUDENT_ATTENDANCE_SUMMARY_TEMPLATE = '1707163646397399883'
DAILY_INSTRUCTOR_ATTENDANCE_REMINDER_TEMPLATE = '1707175947082321519'

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

    # --- OPTIMIZATION 1: JOIN Course table to get course_name directly ---
    q = """
        SELECT
            CS.`name`,
            CS.`schedule_date`,
            CS.`course`,
            CS.`from_time`,
            CS.`to_time`,
            CS.`room`,
            R.`room_name`,
            C.`course_name`,  -- ADDED: Get course_name directly
            CS.`student_group`,
            CS.`color`,
            CS.`class_schedule_color`,
            CS.`instructor`,
            CS.`co_instructor_1`,
            CS.`co_instructor_2`
        FROM
            `tabCourse Schedule` AS CS
        LEFT JOIN `tabRoom` AS R ON CS.room = R.name
        LEFT JOIN `tabCourse` AS C ON CS.course = C.name  -- ADDED: Join with Course table
        WHERE
            (CS.`instructor` = %(instructor)s OR
             CS.`co_instructor_1` = %(instructor)s OR
             CS.`co_instructor_2` = %(instructor)s)
            AND
            CS.`schedule_date` BETWEEN %(start_date)s AND %(end_date)s
        ORDER BY
            CS.`schedule_date` ASC, CS.`from_time` ASC
    """

    course_schedules = frappe.db.sql(q, values={
        "instructor": instructor,
        "start_date": start_date_str,
        "end_date": end_date_str
    }, as_dict=True)

    if not course_schedules:
        return []

    # --- OPTIMIZATION 2: Batch-fetch ALL attendance data in ONE query ---
    course_schedule_ids = [cs.name for cs in course_schedules]
    
    attendance_query = """
        SELECT
            course_schedule,
            status,
            COUNT(*) as count
        FROM
            `tabStudent Attendance`
        WHERE
            course_schedule IN %(schedule_ids)s
            AND docstatus = 1
        GROUP BY
            course_schedule, status
    """
    
    attendance_data = frappe.db.sql(attendance_query, values={
        "schedule_ids": course_schedule_ids
    }, as_dict=True)
    
    # Build attendance lookup dictionary
    attendance_lookup = {}
    for att in attendance_data:
        cs_id = att['course_schedule']
        if cs_id not in attendance_lookup:
            attendance_lookup[cs_id] = {
                'total_students': 0,
                'present_count': 0,
                'absent_count': 0,
                'on_leave_count': 0
            }
        
        status = att['status']
        count = att['count']
        attendance_lookup[cs_id]['total_students'] += count
        
        if status == "Present":
            attendance_lookup[cs_id]['present_count'] = count
        elif status == "Absent":
            attendance_lookup[cs_id]['absent_count'] = count
        elif status == "On Leave":
            attendance_lookup[cs_id]['on_leave_count'] = count
    # --- END OPTIMIZATION 2 ---

    detailed_schedule = []

    for cs_record in course_schedules:
        course_name_val = None
        course_actual_id = None
        calendar_id_val = None
        start_datetime_formatted = None
        end_datetime_formatted = None

        # --- OPTIMIZATION 3: Use pre-fetched attendance data ---
        attendance_summary = attendance_lookup.get(cs_record.name, {})

        # --- OPTIMIZATION 4: Use course_name from JOIN instead of frappe.get_doc ---
        if cs_record.course:
            course_actual_id = cs_record.course
            # Use the course_name from the JOIN query
            course_name_val = cs_record.get('course_name') or f"Unknown Course ({course_actual_id})"
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

        entry = {
            "course_schedule_id": cs_record.name,
            "date": cs_record.schedule_date.strftime('%Y-%m-%d'),
            "course_name": course_name_val,
            "course_id": course_actual_id,
            "calendar_id": calendar_id_val,
            "start_time": start_datetime_formatted,
            "end_time": end_datetime_formatted,
            "room_id": cs_record.get("room"),
            "room_name": cs_record.get("room_name"),
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

    # --- CHANGE 1: DEFINE THE EXCLUSION LIST ---
    # This list contains custom_student_id's that should be temporarily skipped.
    excluded_student_ids = ["25B91A05K6","25B91A5453","25B91A12G3","25B91A6216","25B91A5479","25B91A07B8", "25B91A0554", "25B91A05K6", "25B91A5453", "25B91A6216", "25B91A0793", "25B91A0796", "25B91A0723", "25B91A07C2", "25B91A0718", "25B91A07C4", "25B91A0455", "25B91A0792", "25B91A0344", "25B91A54E8", "25B91A54B7", "25B91A54G8", "25B91A04G0", "25B91A5470"]
    print(f"Exclusion list is active for these IDs: {excluded_student_ids}")
    # ----------------------------------------------

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

            # Fetch student document early to get all necessary details
            student_doc = frappe.get_doc("Student", student_id)
            mobile_no, reg_no = student_doc.get("custom_father_mobile_number"), student_doc.get("custom_student_id")
            
            # --- CHANGE 2: ADD THE EXCLUSION FILTER LOGIC ---
            # This check runs first. If a student is on the list, the loop continues to the next student.
            if reg_no in excluded_student_ids:
                print(f"Skipping student {student_id} ({reg_no}) as they are on the temporary exclusion list.")
                continue
            # ----------------------------------------------------

            # Get student group (original logic preserved)
            student_group = frappe.get_value("Student Attendance", {"student": student_id, "date": processing_date}, "student_group")

            # --- START: Configurable Filter ---
            # Check if student_group matches the configured criteria in DAILY_SUMMARY_REQUIRED_PATTERNS
            # All patterns in DAILY_SUMMARY_REQUIRED_PATTERNS must be present in student_group
            if not student_group:
                print(f"Skipping student {student_id} as student_group is missing.")
                continue

            if DAILY_SUMMARY_REQUIRED_PATTERNS:
                matches_criteria = True
                for pattern in DAILY_SUMMARY_REQUIRED_PATTERNS:
                    if pattern not in student_group:
                        matches_criteria = False
                        break
                
                if not matches_criteria:
                    print(f"Skipping student {student_id} from group '{student_group}' as it does not match criteria {DAILY_SUMMARY_REQUIRED_PATTERNS}.")
                    continue
            # --- END: Configurable Filter ---
            
            # Mobile number check (original logic preserved)
            if not mobile_no:
                print(f"Warning: No mobile number for student {student_id}. Skipping.")
                continue
            if not mobile_no.startswith("91"):
                mobile_no = "91" + mobile_no
            
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

@frappe.whitelist()
def send_instructor_attendance_reminders():
    """
    Scheduled function to find instructors with missed attendance for ACTIVE student groups and send a reminder.
    (Optimized Logic with Filtering)
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
        
        # If the instructor has pending classes, proceed to check if they are relevant.
        if pending_ids:
            
            # ***** MODIFIED SECTION START *****
            # Check if any of the pending classes belong to an active student group.
            
            pending_schedule_groups = frappe.get_all(
                "Course Schedule",
                filters={"name": ["in", list(pending_ids)]},
                fields=["student_group"]
            )
            
            is_relevant_pending = False
            for schedule in pending_schedule_groups:
                student_group = schedule.get("student_group")
                # Check if the group exists and if any active pattern is a substring of the group name
                if student_group and any(pattern in student_group for pattern in ACTIVE_STUDENT_GROUP_PATTERNS_FOR_REMINDERS):
                    is_relevant_pending = True
                    break # A relevant class was found, no need to check further

            # If none of the pending classes were for active groups, skip this instructor.
            if not is_relevant_pending:
                print(f"Skipping instructor {instructor_id}; their {len(pending_ids)} pending classes are for non-active groups.")
                continue
            
            # ***** MODIFIED SECTION END *****

            try:
                print(f"\n--- Processing Instructor: {instructor_id} with relevant pending classes ---")
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
                
                message_id = send_summary_sms_helper(mobile_no, message_text, DAILY_INSTRUCTOR_ATTENDANCE_REMINDER_TEMPLATE)
                # message_id = "INSTRUCTOR_SMS_DISABLED"
                
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

@frappe.whitelist()
def sync_external_attendance(sync_date=None, local_file_path=None):
    """
    Fetches attendance from an external API and UPDATES or INSERTS Frappe records.
    
    Logic:
    - If attendance record exists with different status → UPDATE it
    - If attendance record doesn't exist → INSERT (CREATE) it
    - If attendance record exists but not in API data → LEAVE IT ALONE (no changes)
    
    Morning/Afternoon Classification:
    - Morning: Classes that START before 1:00 PM (from_time < 13:00)
    - Afternoon: Classes that START at or after 1:00 PM (from_time >= 13:00)
    """

    # --- HELPER FUNCTION: This is our robust alternative to get_time_obj ---
    def _to_time_obj(time_val):
        """Converts a string or timedelta into a standard datetime.time object for comparison."""
        if isinstance(time_val, time):
            return time_val
        if isinstance(time_val, timedelta):
            total_seconds = time_val.total_seconds()
            hours = int(total_seconds // 3600) % 24
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            return time(hours, minutes, seconds)
        if isinstance(time_val, str):
            # Attempt to parse HH:MM:SS format
            try:
                return datetime.strptime(time_val, "%H:%M:%S").time()
            except ValueError:
                # Handle other potential string formats if necessary, or return None
                return None
        return None # Return None if the type is unexpected

    # --- Main script starts here ---
    if not sync_date:
        sync_date = today()

    log = frappe.new_doc("External Attendance Sync Log")
    log.sync_date = sync_date
    log.execution_time = now_datetime()
    log.status = "In Progress"
    log.source_api = "https://citi.srkramc.in/controllers/get_crt_attendance.php"
    log.insert(ignore_permissions=True); frappe.db.commit()

    try:
        # --- 1. Fetch data ---
        student_attendance_data = []
        if local_file_path:
            with open(local_file_path, 'r') as f: api_data = json.load(f)
            student_attendance_data = api_data.get("attendance", [])
        else:
            try:
                api_url = f"{log.source_api}?date={sync_date}"
                response = requests.get(api_url, timeout=120)
                response.raise_for_status()
                api_data = response.json()
            except requests.exceptions.RequestException as e: raise ConnectionError(f"API Connection Failed: {e}")
            except json.JSONDecodeError: raise ValueError(f"Invalid JSON response from API. Response text: {response.text[:200]}")
            student_attendance_data = api_data.get("attendance")

        if not student_attendance_data or not isinstance(student_attendance_data, list):
            log.status = "Success"; log.log_details = "API call successful but returned no attendance data."; log.save(); frappe.db.commit()
            return

        # --- 2. Map API IDs to Frappe Student Names ---
        api_student_ids = list({s['student_id'] for s in student_attendance_data if s.get('student_id')})
        student_id_map = {d.custom_student_id: d.name for d in frappe.get_all("Student", filters={"custom_student_id": ["in", api_student_ids]}, fields=["name", "custom_student_id"])}
        frappe_student_names = list(student_id_map.values())
        
        # --- 3. Build the desired state from API data ---
        desired_state = {}
        all_schedules_list = frappe.db.sql("""
            SELECT cs.name AS course_schedule_id, cs.student_group, cs.from_time, sgs.student
            FROM `tabCourse Schedule` AS cs JOIN `tabStudent Group Student` AS sgs ON cs.student_group = sgs.parent
            WHERE sgs.student IN %(names)s AND cs.schedule_date = %(date)s ORDER BY sgs.student, cs.from_time ASC
        """, {"names": frappe_student_names, "date": sync_date}, as_dict=True)

        schedules_by_student = {name: [] for name in frappe_student_names}
        for s in all_schedules_list: schedules_by_student[s.student].append(s)

        one_pm = time(13, 0) # Using the standard Python time object directly

        for student_data in student_attendance_data:
            frappe_student_name = student_id_map.get(student_data.get("student_id"))
            if not frappe_student_name: continue
            
            student_schedules = schedules_by_student.get(frappe_student_name, [])
            # FIXED: Use from_time to classify morning/afternoon
            morning_schedules = [s for s in student_schedules if _to_time_obj(s.from_time) < one_pm]
            afternoon_schedules = [s for s in student_schedules if _to_time_obj(s.from_time) >= one_pm]

            for session_schedules, session_name in [(morning_schedules, "morning"), (afternoon_schedules, "afternoon")]:
                # Handle case where API returns explicit null/None for session data
                session_data = student_data.get(session_name) or {}
                status = str(session_data.get("attendance", "")).title()
                if status in ["Present", "Absent"]:
                    for schedule in session_schedules:
                        desired_state[(frappe_student_name, schedule.course_schedule_id)] = {
                            "status": status, "student_name": student_data.get("student_name"), "student_group": schedule.student_group }
        
        # --- 4. CRITICAL: Detect and remove duplicate attendance records BEFORE processing ---
        # Find all existing attendance records for these students on this date
        all_existing_records = frappe.db.sql("""
            SELECT name, student, course_schedule, status, creation
            FROM `tabStudent Attendance`
            WHERE student IN %(names)s 
            AND date = %(date)s 
            AND docstatus = 1
            ORDER BY student, course_schedule, creation DESC
        """, {"names": frappe_student_names, "date": sync_date}, as_dict=True)
        
        # Identify duplicates and keep only the most recent one
        seen_keys = {}
        duplicates_to_cancel = []
        
        for record in all_existing_records:
            key = (record.student, record.course_schedule)
            if key in seen_keys:
                # This is a duplicate - mark for cancellation
                duplicates_to_cancel.append(record.name)
            else:
                # First occurrence - keep this one
                seen_keys[key] = record
        
        # Cancel duplicate records in bulk
        if duplicates_to_cancel:
            frappe.db.sql("""
                UPDATE `tabStudent Attendance`
                SET docstatus = 2
                WHERE name IN %(names)s
            """, {"names": duplicates_to_cancel})
            frappe.log_error(f"Cancelled {len(duplicates_to_cancel)} duplicate attendance records", "Duplicate Attendance Cleanup")
        
        # --- 5. UPDATE or INSERT logic (no cancellation) ---
        # Now seen_keys contains only unique records (one per student per course_schedule)
        existing_state = {(r.student, r.course_schedule): {"status": r.status, "name": r.name} for r in seen_keys.values()}
        
        records_to_update = []
        docs_to_insert = []
        
        for (student, schedule_id), data in desired_state.items():
            key = (student, schedule_id)
            if key in existing_state:
                # Record exists - check if status needs updating
                if existing_state[key]["status"] != data["status"]:
                    records_to_update.append({
                        "name": existing_state[key]["name"],
                        "status": data["status"]
                    })
            else:
                # Record doesn't exist - create it
                docs_to_insert.append({
                    "doctype": "Student Attendance",
                    "student": student,
                    "student_name": data["student_name"],
                    "status": data["status"],
                    "course_schedule": schedule_id,
                    "student_group": data["student_group"],
                    "date": sync_date,
                    "docstatus": 1
                })
        
        # --- 6. Perform bulk UPDATE (CRITICAL: Bulk operation, not one by one) ---
        if records_to_update:
            # Bulk update using a single SQL statement
            update_cases = []
            update_ids = []
            for record in records_to_update:
                update_ids.append(record["name"])
                update_cases.append(f"WHEN '{record['name']}' THEN '{record['status']}'")
            
            if update_cases:
                sql = f"""
                    UPDATE `tabStudent Attendance`
                    SET status = CASE name
                        {' '.join(update_cases)}
                    END
                    WHERE name IN ({','.join(['%s'] * len(update_ids))})
                """
                frappe.db.sql(sql, update_ids)
        
        # --- 7. Perform bulk INSERT (CRITICAL: Bulk operation with duplicate prevention) ---
        if docs_to_insert:
            # We must generate the 'name' (PK) manually for bulk insert, and standard audit fields.
            current_user = frappe.session.user
            now_str = now_datetime().strftime('%Y-%m-%d %H:%M:%S.%f')
            
            # We must generate the 'name' (PK) manually for bulk insert, and standard audit fields.
            current_user = frappe.session.user
            now_str = now_datetime().strftime('%Y-%m-%d %H:%M:%S.%f')
            
            # --- NAMING STRATEGY ---
            # To ensure the naming is EXACTLY what Frappe would do (including all hooks, defaults, 
            # and current configurations), we create a temporary document object and let it 
            # calculate its own name. This bypasses any need to guess or reverse-engineer logic.
            
            for doc_dict in docs_to_insert:
                # 1. Create a transient object (not saved to DB)
                temp_doc = frappe.get_doc(doc_dict)
                
                # 2. Trigger the standard naming logic
                # This calls set_new_name(), applies 'naming_series', runs 'autoname' hooks, etc.
                if not temp_doc.name:
                    temp_doc.set_new_name()
                
                # 3. Apply the generated values back to our bulk-insert dict
                doc_dict['name'] = temp_doc.name
                doc_dict['naming_series'] = temp_doc.naming_series

                # 4. Standard audit fields
                doc_dict['creation'] = now_str
                doc_dict['modified'] = now_str
                doc_dict['owner'] = current_user
                doc_dict['modified_by'] = current_user

            fields = ["name", "naming_series", "student", "student_name", "status", "course_schedule", "student_group", "date", "docstatus", "creation", "modified", "owner", "modified_by"]
            values = [[doc.get(field) for field in fields] for doc in docs_to_insert]
            
            try:
                # Try Frappe's bulk_insert first
                frappe.db.bulk_insert("Student Attendance", fields=fields, values=values, ignore_duplicates=True)
            except Exception as e:
                # Fallback to direct SQL with duplicate prevention
                # CRITICAL: Use INSERT IGNORE to prevent duplicates
                # Note: placeholders count must match len(fields)
                placeholders = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"] * len(values))
                flat_values = [item for sublist in values for item in sublist]
                
                sql = f"""
                    INSERT IGNORE INTO `tabStudent Attendance` 
                    (`name`, `naming_series`, `student`, `student_name`, `status`, `course_schedule`, `student_group`, `date`, `docstatus`, `creation`, `modified`, `owner`, `modified_by`)
                    VALUES {placeholders}
                """
                frappe.db.sql(sql, flat_values)
        
        # --- 8. Final validation: Ensure no duplicates were created ---
        validation_query = """
            SELECT student, course_schedule, COUNT(*) as count
            FROM `tabStudent Attendance`
            WHERE student IN %(names)s 
            AND date = %(date)s 
            AND docstatus = 1
            GROUP BY student, course_schedule
            HAVING count > 1
        """
        duplicates_check = frappe.db.sql(validation_query, {"names": frappe_student_names, "date": sync_date}, as_dict=True)
        
        if duplicates_check:
            error_msg = f"CRITICAL: Duplicates detected after sync! {len(duplicates_check)} duplicate combinations found."
            frappe.log_error(error_msg, "Duplicate Attendance Error")
            log.status = "Warning"
            log.log_details = f"{error_msg}\nRecords Updated: {len(records_to_update)}\nRecords Created: {len(docs_to_insert)}"
        else:
            log.status = "Success"
            log.log_details = (f"Sync Successful.\nDuplicates Cleaned: {len(duplicates_to_cancel)}\nRecords Updated: {len(records_to_update)}\nRecords Created: {len(docs_to_insert)}\nAPI Students: {len(api_student_ids)} | Frappe Students Found: {len(student_id_map)}")
        
        log.records_processed = len(records_to_update) + len(docs_to_insert)
        log.unmapped_students = len(api_student_ids) - len(student_id_map)
        log.save(); frappe.db.commit()
        return log.name

    except Exception as e:
        frappe.db.rollback(); log.status = "Failed"; log.log_details = f"An error occurred during sync override: \n{frappe.get_traceback()}"; log.save(); frappe.db.commit()
        frappe.log_error("External Attendance Sync Failed", frappe.get_traceback())
        return log.name

@frappe.whitelist()
def send_weekly_attendance_summary():
    """
    Scheduled to run weekly (e.g., Saturday).
    Sends parents a summary of their ward's attendance for that specific week (Mon-Sat).
    """
    # 1. DEFINE SCOPE & TIME FRAME
    processing_date = getdate(today())
    if processing_date.weekday() != 5: # 5 = Saturday
        print("Not a Saturday. Weekly summary will not be sent.")
        return "Not a Saturday. Aborting."

    end_of_week = processing_date
    start_of_week = end_of_week - timedelta(days=5) # Monday
    print(f"--- Running Weekly Attendance Summary for {start_of_week.strftime('%d-%m-%Y')} to {end_of_week.strftime('%d-%m-%Y')} ---")

    # 2. PREVENT DUPLICATE MESSAGES
    log_convention = "Weekly Summary: "
    logs_today = frappe.get_all("SMS Log", filters={"sent_on": processing_date}, pluck="sent_to")
    already_processed = [log.split(log_convention)[1] for log in logs_today if log and log.startswith(log_convention)]
    print(f"Students with weekly summary already sent today: {already_processed}")

    # 3. GET ALL ATTENDANCE DATA FOR THE WEEK IN ONE QUERY
    weekly_data = frappe.db.sql("""
        SELECT student, status, COUNT(*) as count
        FROM `tabStudent Attendance`
        WHERE date BETWEEN %(start_date)s AND %(end_date)s AND docstatus = 1
        GROUP BY student, status
    """, {"start_date": start_of_week, "end_date": end_of_week}, as_dict=True)

    if not weekly_data:
        print("No attendance data found for this week. Exiting.")
        return "No attendance data found for the week."

    # 4. PROCESS DATA INTO A CLEAN LOOKUP DICTIONARY
    summary = {}
    for row in weekly_data:
        student_id = row.student
        if student_id not in summary:
            summary[student_id] = {"Present": 0, "Absent": 0, "On Leave": 0}
        summary[student_id][row.status] = row.count
    
    # 5. GET STUDENT DETAILS (GROUP & CONTACT INFO) IN BULK
    all_students_this_week = list(summary.keys())
    student_details = frappe.get_all(
        "Student",
        filters={"name": ["in", all_students_this_week]},
        fields=["name", "custom_student_id", "custom_father_mobile_number", "student_group"]
    )
    student_map = {s.name: s for s in student_details}

    # 6. LOOP THROUGH STUDENTS, FILTER, AND SEND SMS
    for student_id, attendance in summary.items():
        if student_id in already_processed:
            print(f"Skipping {student_id}, already processed.")
            continue

        student_info = student_map.get(student_id)
        if not student_info:
            continue

        try:
            student_group = student_info.get("student_group")
            # ***** THE MODIFIED LOGIC IS HERE *****
            # If the student has no group, or if their group name does not contain ANY of the patterns, skip them.
            if not student_group or not any(pattern in student_group for pattern in TARGET_STUDENT_GROUP_PATTERNS_FOR_SUMMARIES):
                print(f"Skipping {student_id} from group '{student_group}' - does not match any target pattern.")
                continue
            
            mobile_no = student_info.get("custom_father_mobile_number")
            if not mobile_no:
                print(f"Warning: No mobile number for student {student_id}. Skipping.")
                continue
            if not mobile_no.startswith("91"): mobile_no = "91" + mobile_no

            attended_count = attendance.get("Present", 0)
            total_classes = sum(attendance.values())
            
            if total_classes == 0: continue

            # Construct and send the message
            reg_no = student_info.get("custom_student_id") or student_id
            date_range_str = f"from {start_of_week.strftime('%d-%m')} to {end_of_week.strftime('%d-%m')}"
            message_text = f"Dear Parent, Your ward ({reg_no}) attended {attended_count} out of {total_classes} classes this week {date_range_str}. -Principal, SRKREC"
            
            print(f"To: {mobile_no}, Message: {message_text}")
            message_id = send_summary_sms_helper(mobile_no, message_text, WEEKLY_ATTENDANCE_SUMMARY_TEMPLATE)

            # Log the action
            if message_id:
                frappe.get_doc({
                    "doctype": "SMS Log",
                    "sent_on": processing_date,
                    "message": message_text,
                    "requested_numbers": mobile_no,
                    "sent_to": f"{log_convention}{student_id}"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"Successfully logged weekly summary for {student_id}.")

        except Exception as e:
            print(f"!!! ERROR for student {student_id}: {e}")
            frappe.log_error(frappe.get_traceback(), f"Weekly summary failed for {student_id}")
            frappe.db.rollback()

    print("--- Weekly Attendance Summary complete. ---")
    return "Completed"


@frappe.whitelist()
def send_cumulative_attendance_summary():
    """
    Scheduled to run weekly (e.g., Saturday).
    Sends parents a cumulative summary of attendance from the semester start to date.
    """
    # 1. DEFINE SCOPE & TIME FRAME
    processing_date = getdate(today())
    if processing_date.weekday() != 5: # 5 = Saturday
        print("Not a Saturday. Cumulative summary will not be sent.")
        return "Not a Saturday. Aborting."

    end_of_week = processing_date
    start_of_semester = getdate(SEMESTER_START_DATE)
    print(f"--- Running Cumulative Attendance Summary from {start_of_semester.strftime('%d-%m-%Y')} to {end_of_week.strftime('%d-%m-%Y')} ---")
    
    # 2. PREVENT DUPLICATE MESSAGES
    log_convention = "Cumulative Summary: "
    logs_today = frappe.get_all("SMS Log", filters={"sent_on": processing_date}, pluck="sent_to")
    already_processed = [log.split(log_convention)[1] for log in logs_today if log and log.startswith(log_convention)]
    print(f"Students with cumulative summary already sent today: {already_processed}")

    # 3. GET ALL ATTENDANCE DATA FOR THE SEMESTER IN ONE QUERY
    cumulative_data = frappe.db.sql("""
        SELECT student, status, COUNT(*) as count
        FROM `tabStudent Attendance`
        WHERE date BETWEEN %(start_date)s AND %(end_date)s AND docstatus = 1
        GROUP BY student, status
    """, {"start_date": start_of_semester, "end_date": end_of_week}, as_dict=True)

    if not cumulative_data:
        print("No attendance data found for this semester. Exiting.")
        return "No attendance data found for the semester."

    # 4. PROCESS DATA INTO A CLEAN LOOKUP DICTIONARY
    summary = {}
    for row in cumulative_data:
        student_id = row.student
        if student_id not in summary:
            summary[student_id] = {"Present": 0, "Absent": 0, "On Leave": 0}
        summary[student_id][row.status] = row.count

    # 5. GET STUDENT DETAILS (GROUP & CONTACT INFO) IN BULK
    all_students_in_semester = list(summary.keys())
    student_details = frappe.get_all(
        "Student",
        filters={"name": ["in", all_students_in_semester]},
        fields=["name", "custom_student_id", "custom_father_mobile_number", "student_group"]
    )
    student_map = {s.name: s for s in student_details}

    # 6. LOOP THROUGH STUDENTS, FILTER, AND SEND SMS
    for student_id, attendance in summary.items():
        if student_id in already_processed:
            print(f"Skipping {student_id}, already processed.")
            continue

        student_info = student_map.get(student_id)
        if not student_info:
            continue
        
        try:
            student_group = student_info.get("student_group")
            # ***** THE MODIFIED LOGIC IS HERE *****
            # If the student has no group, or if their group name does not contain ANY of the patterns, skip them.
            if not student_group or not any(pattern in student_group for pattern in TARGET_STUDENT_GROUP_PATTERNS_FOR_SUMMARIES):
                print(f"Skipping {student_id} from group '{student_group}' - does not match any target pattern.")
                continue

            mobile_no = student_info.get("custom_father_mobile_number")
            if not mobile_no:
                print(f"Warning: No mobile number for student {student_id}. Skipping.")
                continue
            if not mobile_no.startswith("91"): mobile_no = "91" + mobile_no

            attended_count = attendance.get("Present", 0)
            total_classes = sum(attendance.values())

            if total_classes == 0: continue
            
            percentage = round((attended_count / total_classes) * 100, 2)
            
            # Construct and send the message
            reg_no = student_info.get("custom_student_id") or student_id
            date_str = end_of_week.strftime('%d-%m-%Y')
            message_text = f"Dear Parent, Your ward's ({reg_no}) cumulative attendance this semester is {percentage}% ({attended_count}/{total_classes} classes) as of {date_str}. -Principal, SRKREC"

            print(f"To: {mobile_no}, Message: {message_text}")
            message_id = send_summary_sms_helper(mobile_no, message_text, CUMULATIVE_ATTENDANCE_SUMMARY_TEMPLATE)

            # Log the action
            if message_id:
                frappe.get_doc({
                    "doctype": "SMS Log",
                    "sent_on": processing_date,
                    "message": message_text,
                    "requested_numbers": mobile_no,
                    "sent_to": f"{log_convention}{student_id}"
                }).insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"Successfully logged cumulative summary for {student_id}.")

        except Exception as e:
            print(f"!!! ERROR for student {student_id}: {e}")
            frappe.log_error(frappe.get_traceback(), f"Cumulative summary failed for {student_id}")
            frappe.db.rollback()
            
    print("--- Cumulative Attendance Summary complete. ---")
    return "Completed"

# 1. Weekly Attendance Summary Template
# Template Name (for your reference): Weekly Attendance Summary
# Template Content:
# code
# Code
# Dear Parent, Your ward ({#var#}) attended {#var#} out of {#var#} classes this week {#var#}. -Principal, SRKREC
# Explanation of Variables:
# {#var#} (1st): Will contain the student's registration number (e.g., "22B01A1234").
# {#var#} (2nd): Will contain the number of classes attended (e.g., "8").
# {#var#} (3rd): Will contain the total classes conducted (e.g., "10").
# {#var#} (4th): Will contain the date range string (e.g., "from 18-05 to 23-05").
    

# 2. Cumulative Attendance Summary Template
# Template Name (for your reference): Cumulative Semester Attendance
# Template Content:
# code
# Code
# Dear Parent, Your ward's ({#var#}) cumulative attendance this semester is {#var#}% ({#var#}/{#var#} classes) as of {#var#}. -Principal, SRKREC
# Explanation of Variables:
# {#var#} (1st): Will contain the student's registration number (e.g., "22B01A1234").
# {#var#} (2nd): Will contain the attendance percentage (e.g., "87.52").
# {#var#} (3rd): Will contain the total classes attended (e.g., "125").
# {#var#} (4th): Will contain the total classes conducted (e.g., "143").
# {#var#} (5th): Will contain the "as of" date (e.g., "23-05-2024").