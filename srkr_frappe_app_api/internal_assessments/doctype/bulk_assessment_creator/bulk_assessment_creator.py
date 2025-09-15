# Copyright (c) 2024, your_name and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BulkAssessmentCreator(Document):
    pass

@frappe.whitelist()
def create_assessments_for_term(academic_term):
    if not academic_term or not frappe.db.exists("Academic Term", academic_term):
        frappe.throw(f"Please select a valid Academic Term. '{academic_term}' not found.")

    frappe.msgprint(f"Starting setup for Academic Term: {academic_term}...", title="Process Started", indicator="blue")
    
    # --- THIS IS THE CORRECTED QUERY ---
    # We now join the Academic Term table to correctly fetch the academic_year.
    
    query = """
        SELECT
            ce.course,
            sgs.parent AS student_group,
            term.academic_year
        FROM
            `tabCourse Enrollment` AS ce
        JOIN
            `tabStudent Group Student` AS sgs ON ce.student = sgs.student
        JOIN
            `tabAcademic Term` AS term ON ce.academic_term = term.name
        WHERE
            ce.academic_term = %(academic_term)s
            AND ce.docstatus = 1
        GROUP BY
            ce.course, sgs.parent, term.academic_year
    """
    
    combinations = frappe.db.sql(query, {"academic_term": academic_term}, as_dict=True)

    if not combinations:
        frappe.msgprint(f"No active course enrollments linked to student groups found for Academic Term: {academic_term}", title="No Enrollments", indicator="orange")
        return
    
    # --- THE REST OF THE SCRIPT REMAINS THE SAME ---
    
    default_structure = [
        {'midterm': 'Mid-1', 'assessment_type': 'Objective', 'question_id': 'M1-Obj-Q1', 'co_number': 'CO1', 'max_marks': 2},
        {'midterm': 'Mid-1', 'assessment_type': 'Objective', 'question_id': 'M1-Obj-Q2', 'co_number': 'CO1', 'max_marks': 2},
        {'midterm': 'Mid-1', 'assessment_type': 'Objective', 'question_id': 'M1-Obj-Q3', 'co_number': 'CO2', 'max_marks': 2},
        {'midterm': 'Mid-1', 'assessment_type': 'Objective', 'question_id': 'M1-Obj-Q4', 'co_number': 'CO2', 'max_marks': 2},
        {'midterm': 'Mid-1', 'assessment_type': 'Objective', 'question_id': 'M1-Obj-Q5', 'co_number': 'CO3', 'max_marks': 2},
        {'midterm': 'Mid-1', 'assessment_type': 'Subjective', 'question_id': 'M1-Subj-Q1', 'co_number': 'CO1', 'max_marks': 5},
        {'midterm': 'Mid-1', 'assessment_type': 'Subjective', 'question_id': 'M1-Subj-Q2', 'co_number': 'CO2', 'max_marks': 5},
        {'midterm': 'Mid-1', 'assessment_type': 'Subjective', 'question_id': 'M1-Subj-Q3', 'co_number': 'CO3', 'max_marks': 5},
        {'midterm': 'Mid-1', 'assessment_type': 'Assignment', 'question_id': 'M1-Asgn-Q1', 'co_number': 'CO1', 'max_marks': 3},
        {'midterm': 'Mid-1', 'assessment_type': 'Assignment', 'question_id': 'M1-Asgn-Q2', 'co_number': 'CO1', 'max_marks': 3},
        {'midterm': 'Mid-1', 'assessment_type': 'Assignment', 'question_id': 'M1-Asgn-Q3', 'co_number': 'CO2', 'max_marks': 3},
        {'midterm': 'Mid-1', 'assessment_type': 'Assignment', 'question_id': 'M1-Asgn-Q4', 'co_number': 'CO2', 'max_marks': 3},
        {'midterm': 'Mid-1', 'assessment_type': 'Assignment', 'question_id': 'M1-Asgn-Q5', 'co_number': 'CO3', 'max_marks': 3},
        {'midterm': 'Mid-2', 'assessment_type': 'Objective', 'question_id': 'M2-Obj-Q1', 'co_number': 'CO4', 'max_marks': 2},
        {'midterm': 'Mid-2', 'assessment_type': 'Objective', 'question_id': 'M2-Obj-Q2', 'co_number': 'CO4', 'max_marks': 2},
        {'midterm': 'Mid-2', 'assessment_type': 'Objective', 'question_id': 'M2-Obj-Q3', 'co_number': 'CO5', 'max_marks': 2},
        {'midterm': 'Mid-2', 'assessment_type': 'Objective', 'question_id': 'M2-Obj-Q4', 'co_number': 'CO5', 'max_marks': 2},
        {'midterm': 'Mid-2', 'assessment_type': 'Objective', 'question_id': 'M2-Obj-Q5', 'co_number': 'CO5', 'max_marks': 2},
        {'midterm': 'Mid-2', 'assessment_type': 'Subjective', 'question_id': 'M2-Subj-Q1', 'co_number': 'CO4', 'max_marks': 5},
        {'midterm': 'Mid-2', 'assessment_type': 'Subjective', 'question_id': 'M2-Subj-Q2', 'co_number': 'CO5', 'max_marks': 5},
        {'midterm': 'Mid-2', 'assessment_type': 'Subjective', 'question_id': 'M2-Subj-Q3', 'co_number': 'CO5', 'max_marks': 5},
        {'midterm': 'Mid-2', 'assessment_type': 'Assignment', 'question_id': 'M2-Asgn-Q1', 'co_number': 'CO4', 'max_marks': 3},
        {'midterm': 'Mid-2', 'assessment_type': 'Assignment', 'question_id': 'M2-Asgn-Q2', 'co_number': 'CO4', 'max_marks': 3},
        {'midterm': 'Mid-2', 'assessment_type': 'Assignment', 'question_id': 'M2-Asgn-Q3', 'co_number': 'CO5', 'max_marks': 3},
        {'midterm': 'Mid-2', 'assessment_type': 'Assignment', 'question_id': 'M2-Asgn-Q4', 'co_number': 'CO5', 'max_marks': 3},
        {'midterm': 'Mid-2', 'assessment_type': 'Assignment', 'question_id': 'M2-Asgn-Q5', 'co_number': 'CO5', 'max_marks': 3},
    ]

    created_count = 0
    skipped_count = 0

    for combo in combinations:
        if frappe.db.exists("Semester Midterm Assessment", {
            "academic_term": academic_term,
            "course": combo.course,
            "student_group": combo.student_group
        }):
            skipped_count += 1
            continue

        try:
            doc = frappe.new_doc("Semester Midterm Assessment")
            doc.academic_year = combo.academic_year
            doc.academic_term = academic_term
            doc.student_group = combo.student_group
            doc.course = combo.course
            
            for structure_row in default_structure:
                doc.append("assessment_structure", structure_row)

            doc.save(ignore_permissions=True)
            created_count += 1

        except Exception as e:
            frappe.log_error(message=frappe.get_traceback(), title=f"Bulk Assessment Creator Failed for {combo.course}")

    frappe.db.commit()
    frappe.msgprint(
        f"Semester Assessment Setup Complete.<br>"
        f"<b>Successfully created:</b> {created_count} assessments.<br>"
        f"<b>Skipped (Duplicates):</b> {skipped_count} combinations.",
        title="Success",
        indicator="green"
    )