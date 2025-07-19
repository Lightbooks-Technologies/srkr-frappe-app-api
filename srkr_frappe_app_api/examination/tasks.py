import frappe
from frappe.utils import get_sites
from srkr_frappe_app_api.examination.api import sync_student_exam_results

# This function is called daily by the scheduler, as defined in hooks.py
def sync_all_active_students():
    """
    Scheduled task to sync exam results for all active students who have a student ID.
    This runs in the background for a specific site.
    """
    try:
        # Get all students who are 'Enabled' and have a 'custom_student_id'
        active_students = frappe.get_all(
            "Student",
            filters={
                "enabled": 1,
                "custom_student_id": ["is", "set"],
            },
            fields=["name", "student_name", "custom_student_id"]
        )

        total_students = len(active_students)
        if total_students == 0:
            print("No active students with Student IDs found to sync.")
            return

        print(f"Starting scheduled sync for {total_students} active students...")
        
        success_count = 0
        error_count = 0
        
        # We need to impersonate a user to run the sync, 'Administrator' is a safe choice.
        # This also ensures the 'synced_by' field is populated correctly.
        original_user = frappe.session.user
        frappe.set_user("Administrator")

        for i, student in enumerate(active_students):
            try:
                print(f"Syncing student {i+1}/{total_students}: {student.student_name} ({student.custom_student_id})")
                
                # We call the main sync function silently to avoid pop-up messages in the background job
                frappe.call(
                    'srkr_frappe_app_api.examination.api.sync_student_exam_results',
                    student_id=student.name
                )
                
                # The frappe.call above already commits, but we can add a commit here for safety
                # in case the called function's commit behavior changes.
                frappe.db.commit()
                success_count += 1
            except Exception as e:
                error_count += 1
                # Log the specific error for this student
                frappe.log_error(
                    message=f"Failed to sync results for Student: {student.name} ({student.student_name}). Error: {e}",
                    title="Scheduled Exam Sync Error"
                )
                # Rollback any partial changes for this failed student
                frappe.db.rollback()
        
        # Restore the original user
        frappe.set_user(original_user)
        
        # Log a summary of the entire job
        summary_message = f"Scheduled exam sync completed. Success: {success_count}, Failed: {error_count}"
        print(summary_message)
        frappe.log_error(message=summary_message, title="Scheduled Exam Sync Summary")
        
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(message=frappe.get_traceback(), title="Fatal Error in Scheduled Exam Sync")