# --- FINAL-FINAL VERSION of api.py ---

import frappe
import requests
from frappe import _
from datetime import datetime

# Disable the insecure request warning that verify=False causes
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Main Sync Function ---

@frappe.whitelist()
def sync_student_exam_results(student_id):
    """
    Sync all examination results for a student from SRKR API.
    Makes a single API call to get all available data.
    """
    try:
        student_doc = frappe.get_doc("Student", student_id)
        reg_no = student_doc.get("custom_student_id")
        if not reg_no:
            frappe.throw(_("Student ID (Hall Ticket Number) not found for student {0}").format(student_doc.student_name))

        api_key = frappe.conf.get("srkr_api_key")
        if not api_key:
            frappe.throw(_("SRKR API Key is not configured."))

        headers = {"x-api-key": api_key}
        
        # --- SINGLE API CALL ---
        print(f"--- MAKING SINGLE API CALL for {reg_no} ---")
        url = "https://api.srkrexams.in/api/Result/GetResultByRegNo"
        params = {"regNo": reg_no, "sSEM": "ALL"}
        response = requests.get(url, params=params, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        
        api_data = response.json()
        if not api_data.get("success") or not api_data.get("data"):
            frappe.msgprint(_("API returned no data for this student."))
            return {"status": "success", "data": {"regular_results": 0, "backlogs": 0, "honors_minors": 0}}

        # Extract the main data object
        data_payload = api_data.get("data", {})
        
        # --- Process the single response ---
        sync_results = {}
        sync_results["regular_results"] = _process_regular_results(student_id, reg_no, data_payload)
        sync_results["backlogs"] = _process_backlogs(student_id, reg_no, data_payload)
        # We can add honors/minors here if we discover the key for it later
        sync_results["honors_minors"] = 0 

        frappe.db.commit()

        frappe.msgprint(
            _("Sync completed for {0}:<br>"
              "- Regular Results: {1} semesters synced<br>"
              "- Backlogs: {2} semesters synced<br>"
              "- Honors/Minors: {3} semesters synced").format(
                student_doc.student_name,
                sync_results["regular_results"],
                sync_results["backlogs"],
                sync_results["honors_minors"]
            ),
            indicator="green",
            title=_("Sync Successful")
        )
        
        return {"status": "success", "data": sync_results}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SRKR Exam Results Sync Error")
        frappe.throw(_("An error occurred during the sync process: {0}").format(str(e)))


# --- Helper Processing Functions ---

def _process_regular_results(student_id, reg_no, data_payload):
    """Processes regular semester results from the main API payload."""
    student_info = data_payload.get("student", {})
    results = data_payload.get("Results", []) # Capital 'R'
    synced_count = 0

    if not results: return 0

    for sem_result in results:
        doc = _create_or_get_doc("Exam Semester Result", {"student": student_id, "semester_number": sem_result.get("semester")})
        doc.student, doc.student_id, doc.semester_number = student_id, reg_no, sem_result.get("semester")
        doc.course, doc.branch = student_info.get("course"), student_info.get("branch")
        doc.sgpa, doc.cgpa = sem_result.get("sgpa", 0), sem_result.get("cgpa", 0)
        doc.total_credits, doc.credits_secured = sem_result.get("totalCredits", 0), sem_result.get("creditsSecured", 0)
        
        failed_count = 0
        doc.set("subjects", [])
        for subject in sem_result.get("subjects", []):
            if subject.get("result") == "FAIL": failed_count += 1
            doc.append("subjects", { "subject_code": subject.get("code"), "subject_name": subject.get("name"), "credits": subject.get("credits", 0), "grade": subject.get("grade"), "result": subject.get("result"), "exammy": subject.get("exammy") })
        
        doc.pending_subjects, doc.exam_status = failed_count, "Has Backlogs" if failed_count > 0 else "All Clear"
        _save_doc(doc)
        synced_count += 1
    return synced_count

def _process_backlogs(student_id, reg_no, data_payload):
    """Processes backlog information from the main API payload."""
    backlogs_data = data_payload.get("backlogs", []) # lowercase 'b'
    synced_count = 0

    if not backlogs_data: return 0
    
    # Clear all old backlogs for this student first
    existing_backlogs = frappe.get_all("Exam Semester Backlog", filters={"student": student_id}, pluck="name")
    for item in existing_backlogs:
        frappe.delete_doc("Exam Semester Backlog", item, ignore_permissions=True, force=True)

    for sem_backlog in backlogs_data:
        if not sem_backlog.get("subjects"): continue
        doc = frappe.new_doc("Exam Semester Backlog")
        doc.student, doc.student_id, doc.semester_number = student_id, reg_no, sem_backlog.get("semester")
        doc.total_backlogs = len(sem_backlog.get("subjects", []))
        doc.set("backlog_subjects", [])
        for subject in sem_backlog.get("subjects", []):
            doc.append("backlog_subjects", { "subject_code": subject.get("code"), "subject_name": subject.get("name"), "exammy": subject.get("exammy") })
        _save_doc(doc)
        synced_count += 1
    return synced_count


# --- Utility Functions ---

def _create_or_get_doc(doctype, filters):
    existing = frappe.db.exists(doctype, filters)
    return frappe.get_doc(doctype, existing) if existing else frappe.new_doc(doctype)

def _save_doc(doc):
    doc.last_synced, doc.synced_by = datetime.now(), frappe.session.user
    frappe.flags.in_import = True
    doc.save(ignore_permissions=True)
    frappe.flags.in_import = False

@frappe.whitelist()
def get_student_exam_summary(student_id):
    if not student_id: return {}
    summary = {}
    latest_result = frappe.db.get_value("Exam Semester Result", {"student": student_id}, ["cgpa", "semester_number"], order_by="semester_number desc")
    if latest_result:
        summary["latest_cgpa"], summary["latest_semester"] = latest_result[0], latest_result[1]
    total_backlogs = frappe.db.sql("SELECT SUM(total_backlogs) FROM `tabExam Semester Backlog` WHERE student = %s", (student_id,))
    summary["total_backlogs"] = total_backlogs[0][0] if total_backlogs and total_backlogs[0][0] else 0
    return summary