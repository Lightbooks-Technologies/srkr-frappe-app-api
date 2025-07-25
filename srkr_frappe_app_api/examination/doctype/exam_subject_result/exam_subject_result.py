# Copyright (c) 2024, Lightbooks and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ExamSubjectResult(Document):
    def validate(self):
        # Prevent any modification
        if not self.is_new() and not frappe.flags.in_import:
            frappe.throw("Examination results are read-only and cannot be modified.")