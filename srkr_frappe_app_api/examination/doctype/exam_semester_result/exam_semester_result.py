# Copyright (c) 2024, Lightbooks and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ExamSemesterResult(Document):
    def validate(self):
        # This part is fine, no changes needed
        if not self.is_new() and not frappe.flags.in_import:
            frappe.throw("Official Examination Results are read-only and cannot be modified after being synced.")
    
    # --- THIS IS THE CORRECTED METHOD ---
    def has_permission(self, ptype, user=None):
        # If no user is passed, default to the logged-in user
        if not user:
            user = frappe.session.user

        # Allow System Manager and Administrator full access based on their Role Permissions
        if "System Manager" in frappe.get_roles(user) or "Administrator" == user:
            return True
        
        # Custom logic for read permissions
        if ptype == "read":
            # Academic Users can read all results
            if "Academic User" in frappe.get_roles(user):
                return True
            
            # Students can only read results linked to their user account
            if "Student" in frappe.get_roles(user):
                student_linked_to_this_record = self.student
                email_of_logged_in_user = user
                
                # Check if the logged-in user is the one associated with this student record
                student_doc_of_user = frappe.db.get_value("Student", {"student_email_id": email_of_logged_in_user}, "name")
                
                if student_linked_to_this_record == student_doc_of_user:
                    return True
        
        # By default, if no rule matches, deny permission
        return False