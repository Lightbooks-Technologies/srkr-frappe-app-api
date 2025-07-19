# Copyright (c) 2024, Lightbooks and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ExamHmSemesterResult(Document):
    def validate(self):
        if not self.is_new() and not frappe.flags.in_import:
            frappe.throw("Official Examination Results are read-only and cannot be modified after being synced.")
    
    def has_permission(self, ptype, user=None):
        if not user:
            user = frappe.session.user

        if "System Manager" in frappe.get_roles(user) or "Administrator" == user:
            return True
        
        if ptype == "read":
            if "Academic User" in frappe.get_roles(user):
                return True
            
            if "Student" in frappe.get_roles(user):
                student_doc_of_user = frappe.db.get_value("Student", {"student_email_id": user}, "name")
                if self.student == student_doc_of_user:
                    return True
        
        return False