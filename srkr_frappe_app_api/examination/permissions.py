import frappe

def get_permission_query_conditions(user=None):
    """
    Restricts access to examination documents based on user roles.
    - System Manager & Academic User: Can see all records.
    - Student: Can only see their own records.
    - Other roles: Cannot see any records.
    
    This function is called by the hook 'permission_query_conditions' in hooks.py.
    """
    if not user:
        user = frappe.session.user

    # Administrators can see everything, no conditions needed.
    if user == "Administrator":
        return ""

    roles = frappe.get_roles(user)

    # If the user has these roles, they can see all records.
    if "System Manager" in roles or "Academic User" in roles:
        return ""

    # If the user is a Student, restrict them to their own documents.
    if "Student" in roles:
        # Get the student record linked to the logged-in user's email
        student_doc_name = frappe.db.get_value("Student", {"student_email_id": user}, "name")
        
        if student_doc_name:
            # This condition will be applied to the query for any of the linked DocTypes
            # (Exam Semester Result, Exam Semester Backlog, etc.)
            # We use frappe.db.escape to prevent SQL injection.
            return f"student = {frappe.db.escape(student_doc_name)}"
        else:
            # If no student is linked to this user, they can't see any exam records.
            # "1=0" is a standard SQL trick for returning no results.
            return "1=0"

    # For any other user role, deny access by default.
    return "1=0"