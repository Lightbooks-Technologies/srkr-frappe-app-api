import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def ensure_student_custom_fields():
    """
    Checks if the 'custom_student_id' field exists on the Student DocType
    and creates it if it doesn't. This is meant to be run once from the bench console.
    """
    if frappe.db.exists("Custom Field", {"dt": "Student", "fieldname": "custom_student_id"}):
        frappe.msgprint("Custom field 'custom_student_id' already exists on Student DocType. No action taken.")
        return

    print("Creating custom field 'custom_student_id' on Student DocType...")
    
    custom_fields_to_create = {
        "Student": [
            {
                "fieldname": "custom_student_id",
                "label": "Student ID (Hall Ticket)",
                "fieldtype": "Data",
                "insert_after": "student_email_id",
                "unique": 1,
                "description": "Official SRKR Hall Ticket Number / Registration Number",
                "in_list_view": 1,
                "in_standard_filter": 1,
                "no_copy": 1
            }
        ]
    }
    
    create_custom_fields(custom_fields_to_create)
    print("Custom field 'custom_student_id' created successfully.")
    frappe.msgprint("Successfully created custom field 'custom_student_id' on Student DocType.")