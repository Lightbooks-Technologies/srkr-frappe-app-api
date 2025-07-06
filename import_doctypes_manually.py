import frappe
import os
import json

def import_doctypes_manually():
    """
    This script explicitly imports the DocTypes when `bench migrate` doesn't recognize them.
    Uses the same approach that worked in the console.
    """
    print("\n--- Manual DocType Import ---")
    
    MODULE = "Education"
    
    # --- Part 1: Forceful Cleanup ---
    for dt in ("Subject Result", "Semester Result"):
        if frappe.db.exists("DocType", dt):
            frappe.delete_doc("DocType", dt, force=1, ignore_permissions=True)
            print(f"'{dt}' forcefully deleted.")
    frappe.db.commit()
    print("Cleanup committed.\n")
    
    # --- Part 2: Create Child Table ---
    if not frappe.db.exists("DocType", "Subject Result"):
        print("Creating 'Subject Result' child table...")
        subject_meta = {
            "doctype": "DocType",
            "name": "Subject Result",
            "module": MODULE,
            "custom": 1,
            "istable": 1,
            "naming_rule": "Random",
            "autoname": "hash",
            "fields": [
                {"label": "Course",        "fieldname": "course",        "fieldtype": "Link",  "options": "Course"},
                {"label": "Subject Code",  "fieldname": "subject_code",  "fieldtype": "Data",  "in_list_view": 1},
                {"label": "Subject Name",  "fieldname": "subject_name",  "fieldtype": "Data",  "in_list_view": 1},
                {"label": "Credits",       "fieldname": "credits",       "fieldtype": "Float", "in_list_view": 1},
                {"label": "Grade",         "fieldname": "grade",         "fieldtype": "Data",  "in_list_view": 1},
                {"label": "Result",        "fieldname": "result",        "fieldtype": "Select","options": "PASS\nFAIL", "in_list_view": 1},
                {"label": "Exam Session",  "fieldname": "exam_session",  "fieldtype": "Data",  "description": "e.g., APR-2022"},
            ]
        }
        frappe.get_doc(subject_meta).insert(ignore_permissions=True)
        frappe.db.commit()
        print("'Subject Result' created and committed.")

        # Clear cache so Frappe picks up istable=1 immediately
        print("Reloading 'Subject Result' metadata...")
        frappe.reload_doctype("Subject Result")
        print("Metadata reloaded.\n")

    # --- Part 3: Create Parent Table ---
    if not frappe.db.exists("DocType", "Semester Result"):
        print("Creating 'Semester Result' parent table...")
        semester_meta = {
            "doctype": "DocType",
            "name": "Semester Result",
            "module": MODULE,
            "custom": 1,
            "naming_rule": "Expression",
            "autoname": "SR-.student.-.{semester}",
            "title_field": "student",
            "fields": [
                {"label": "Student",        "fieldname": "student",        "fieldtype": "Link",  "options": "Student",  "reqd": 1, "in_list_view": 1},
                {"label": "Semester",       "fieldname": "semester",       "fieldtype": "Link",  "options": "Semester", "reqd": 1, "in_list_view": 1},
                {"label": "Regulation",     "fieldname": "regulation",     "fieldtype": "Link",  "options": "Regulation"},
                {"label": "Result Type",    "fieldname": "result_type",    "fieldtype": "Select","options": "Regular\nHonors and Minors","default":"Regular"},
                {"fieldname": "col_break_1","fieldtype": "Column Break"},
                {"label": "SGPA",           "fieldname": "sgpa",           "fieldtype": "Float", "precision": 2, "in_list_view": 1},
                {"label": "CGPA",           "fieldname": "cgpa",           "fieldtype": "Float", "precision": 2, "in_list_view": 1},
                {"label": "Total Credits",  "fieldname": "total_credits",  "fieldtype": "Float", "precision": 2},
                {"label": "Credits Secured","fieldname": "credits_secured","fieldtype": "Float", "precision": 2},
                {"fieldname": "sec_break_1","fieldtype": "Section Break", "label": "Subjects"},
                {"label": "Subjects",       "fieldname": "subjects",       "fieldtype": "Table", "options": "Subject Result"},
                {"fieldname": "sec_break_2","fieldtype": "Section Break", "label": "Attachments"},
                {"label": "Result PDF",     "fieldname": "result_pdf",     "fieldtype": "Attach"},
                {"label": "API Response URL","fieldname": "api_url",       "fieldtype": "Data"},
            ],
            "permissions": [
                {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1},
                {"role": "Student",        "read": 1}
            ]
        }
        frappe.get_doc(semester_meta).insert(ignore_permissions=True)
        print("'Semester Result' created.")

    frappe.db.commit()
    print("\n✅ All DocTypes rebuilt successfully.")

if __name__ == "__main__":
    import_doctypes_manually()
