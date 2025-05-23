import frappe
from frappe import _
from frappe.utils import getdate, add_days, formatdate
import calendar
from education.education.doctype.course_scheduling_tool.course_scheduling_tool import CourseSchedulingTool
from education.education.utils import OverlapError

class CustomCourseSchedulingTool(CourseSchedulingTool):
    @frappe.whitelist()
    def schedule_course(self, days):
        """
        Custom schedule_course method that skips holidays
        """
        frappe.msgprint("🎯 Custom schedule_course method called - Checking for holidays")
        
        # Get the holiday list
        holiday_dates = self.get_holiday_dates()
        
        if holiday_dates:
            frappe.msgprint(f"📅 Found {len(holiday_dates)} holidays to skip")
        
        # Call our custom logic that follows the original structure
        return self.schedule_course_with_holiday_skip(days, holiday_dates)
    
    def get_holiday_dates(self):
        """
        Get all holiday dates from the first available holiday list
        """
        try:
            # Get the first holiday list (since you mentioned there's only one)
            holiday_list = frappe.get_all("Holiday List", 
                                        fields=["name"], 
                                        limit=1)
            
            if not holiday_list:
                frappe.msgprint("⚠️ No holiday list found")
                return []
            
            holiday_list_name = holiday_list[0].name
            frappe.msgprint(f"📋 Using holiday list: {holiday_list_name}")
            
            # Get all holidays from this list
            holidays = frappe.get_all("Holiday", 
                                    filters={"parent": holiday_list_name},
                                    fields=["holiday_date", "description"],
                                    order_by="holiday_date")
            
            holiday_dates = [holiday.holiday_date for holiday in holidays]
            
            # Log holiday dates for debugging
            if holiday_dates:
                frappe.logger().info(f"Holiday dates found: {holiday_dates}")
                holiday_info = [f"{formatdate(h.holiday_date)} - {h.description}" for h in holidays]
                frappe.msgprint(f"Holidays to skip: {', '.join(holiday_info[:5])}...")  # Show first 5
            
            return holiday_dates
            
        except Exception as e:
            frappe.logger().error(f"Error getting holiday dates: {str(e)}")
            frappe.msgprint(f"⚠️ Error getting holidays: {str(e)}")
            return []
    
    def schedule_course_with_holiday_skip(self, days, holiday_dates):
        """
        Create course schedules while skipping holidays - following original method structure
        """
        course_schedules = []
        course_schedules_errors = []
        rescheduled = []
        reschedule_errors = []
        skipped_holidays = []

        # Validate like the original method
        self.validate_mandatory(days)
        self.validate_date()
        self.instructor_name = frappe.db.get_value(
            "Instructor", self.instructor, "instructor_name"
        )

        group_based_on, course = frappe.db.get_value(
            "Student Group", self.student_group, ["group_based_on", "course"]
        )

        if group_based_on == "Course":
            self.course = course

        if self.reschedule:
            rescheduled, reschedule_errors = self.delete_course_schedule(
                rescheduled, reschedule_errors, days
            )

        # Main scheduling loop with holiday checking
        date = self.course_start_date
        while date < self.course_end_date:
            day_name = calendar.day_name[getdate(date).weekday()]
            
            if day_name in days:
                # Check if this date is a holiday
                if getdate(date) in holiday_dates:
                    skipped_holidays.append(formatdate(date))
                    frappe.logger().info(f"Skipping holiday: {formatdate(date)}")
                else:
                    # Create course schedule for non-holiday (using original method)
                    course_schedule = self.make_course_schedule(date)
                    try:
                        course_schedule.save()
                    except OverlapError:
                        course_schedules_errors.append(date)
                    else:
                        course_schedules.append(course_schedule)

            date = add_days(date, 1)

        # Show summary with holiday information
        summary_msg = f"✅ Created {len(course_schedules)} course schedules"
        if skipped_holidays:
            summary_msg += f" 🚫 Skipped {len(skipped_holidays)} holidays: {', '.join(skipped_holidays)}"
        if course_schedules_errors:
            summary_msg += f" ⚠️ {len(course_schedules_errors)} scheduling conflicts"
        
        frappe.msgprint(summary_msg)

        # Return in exact same format as original
        return dict(
            course_schedules=course_schedules,
            course_schedules_errors=course_schedules_errors,
            rescheduled=rescheduled,
            reschedule_errors=reschedule_errors,
        )