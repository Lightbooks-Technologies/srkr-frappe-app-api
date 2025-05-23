import frappe
from frappe import _
from education.education.doctype.course_scheduling_tool.course_scheduling_tool import CourseSchedulingTool

class CustomCourseSchedulingTool(CourseSchedulingTool):
    @frappe.whitelist()
    def schedule_course(self, days):
        """
        Override the original schedule_course method with custom logic
        """
        print("Custom schedule_course method called")
        # Your custom logic here
        frappe.msgprint("Custom schedule_course method called")
        
        # You can call the original method if needed:
        # super().schedule_course(days)
        
        # Or implement completely custom logic:
        # Add your custom scheduling logic here
        
        return {
            "message": "Custom scheduling completed",
            "status": "success"
        }