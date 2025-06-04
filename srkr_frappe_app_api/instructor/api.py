import frappe
from frappe.utils import getdate # Only getdate is strictly needed from utils for this one
import re 
from datetime import timedelta, datetime as dt

@frappe.whitelist()
def get_instructor_schedule(instructor, start_date, end_date=None):
    if not instructor or not start_date:
        frappe.throw("Instructor ID and Start Date are required.")

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
        end_date_str = start_date_str # Default to single day query

    if getdate(start_date_str) > getdate(end_date_str):
        frappe.throw("Start Date cannot be after End Date.")
    # --- (End of Date validation) ---

    schedule_filters = [
        ["instructor", "=", instructor],
        ["schedule_date", "between", [start_date_str, end_date_str]],
    ]
    
    schedule_fields = [
        "name", 
        "schedule_date",
        "course", 
        "from_time",
        "to_time",
        "room", 
        "student_group",
        "color", 
    ]
    
    course_schedules = frappe.get_all(
        "Course Schedule",
        filters=schedule_filters,
        fields=schedule_fields,
        order_by="schedule_date asc, from_time asc"
    )

    if not course_schedules:
        return [] 

    detailed_schedule = []

    for cs_record in course_schedules:
        course_name_val = None
        course_actual_id = None
        calendar_id_val = None
        start_datetime_formatted = None 
        end_datetime_formatted = None   
        
        if cs_record.course:
            course_actual_id = cs_record.course
            try:
                course_doc = frappe.get_doc("Course", course_actual_id)
                course_name_val = course_doc.course_name
                
                if course_actual_id: 
                    temp_id = str(course_actual_id).lower().strip() 
                    calendar_id_val = re.sub(r'\s+', '_', temp_id)
                        
            except frappe.DoesNotExistError:
                course_name_val = f"Unknown Course ({course_actual_id})"
                if course_actual_id:
                    temp_id = str(course_actual_id).lower().strip()
                    calendar_id_val = re.sub(r'\s+', '_', temp_id)
            except Exception:
                course_name_val = f"Error fetching course ({course_actual_id})"
                if course_actual_id:
                    temp_id = str(course_actual_id).lower().strip()
                    calendar_id_val = re.sub(r'\s+', '_', temp_id)
        else:
            course_name_val = "Course Not Specified"

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
            "room": cs_record.get("room"),
            "student_group": cs_record.get("student_group"),
            "color": schedule_color
        }
        detailed_schedule.append(entry)

    return detailed_schedule