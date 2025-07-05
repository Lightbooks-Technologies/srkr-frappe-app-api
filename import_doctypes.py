import frappe
import os
import json
from frappe.modules.import_file import import_file_by_path

def import_doctypes_manually():
    """
    This script explicitly imports the DocTypes when `bench migrate` doesn't recognize them.
    """
    print("\n--- Manual DocType Import ---")
    
    app_path = frappe.get_app_path("srkr_frappe_app_api")
    import_paths = [
        os.path.join(app_path, "doctype/semester_result/semester_result.json"),
        os.path.join(app_path, "doctype/subject_result/subject_result.json")
    ]
    
    for import_path in import_paths:
        try:
            # Check if file exists
            if not os.path.exists(import_path):
                print(f"    ❌ File not found: {import_path}")
                continue
                
            # Read file content
            with open(import_path, 'r') as f:
                doc_content = json.load(f)
            
            # Create the DocType
            if not frappe.db.exists("DocType", doc_content.get("name")):
                import_file_by_path(import_path, force=True)
                print(f"    ✅ Successfully imported: {doc_content.get('name')}")
            else:
                print(f"    ⚪️ DocType already exists: {doc_content.get('name')}")
        except Exception as e:
            print(f"    ❌ Error importing {import_path}: {str(e)}")
    
    print("--- Manual Import Complete ---")

if __name__ == "__main__":
    import_doctypes_manually()
