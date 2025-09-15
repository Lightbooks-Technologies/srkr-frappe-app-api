# Copyright (c) 2024, your_name and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    # --- Step 1: Validate Filters and Fetch Master Document ---
    if not filters or not filters.get("assessment"):
        return [], []

    assessment_doc_name = filters.get("assessment")
    
    try:
        doc = frappe.get_doc("Semester Midterm Assessment", assessment_doc_name)
    except frappe.DoesNotExistError:
        frappe.throw(f"Semester Midterm Assessment '{assessment_doc_name}' not found.")
        return [], []

    # --- Step 2: Dynamically Define the Report Columns ---
    columns = [
        {"fieldname": "register_number", "label": "Register Number", "fieldtype": "Data", "width": 150},
        {"fieldname": "student_name", "label": "Student Name", "fieldtype": "Data", "width": 250},
    ]
    
    # This will hold the mapping from the descriptive header to a simplified fieldname for the report
    column_header_to_fieldname = {}

    # Loop through the defined structure to build the dynamic columns
    for item in doc.assessment_structure:
        # The header the user sees, e.g., "Mid-1-Objective-Q1"
        descriptive_header = f"{item.midterm}-{item.assessment_type}-{item.question_id}"
        # A simplified, safe fieldname for the column, e.g., "mid_1_objective_q1"
        fieldname = descriptive_header.lower().replace('-', '_')

        columns.append({
            "fieldname": fieldname,
            "label": descriptive_header,
            "fieldtype": "Float",
            "width": 120
        })
        column_header_to_fieldname[descriptive_header] = fieldname

    # --- Step 3: Fetch and Prepare the Raw Marks Data for Fast Lookup ---
    
    # Fetch all raw marks for this assessment in one query
    raw_marks = frappe.get_all(
        "Student Marks Data",
        filters={"parent": doc.name},
        fields=["student", "assessment_item", "marks_obtained"]
    )

    # Create a map of assessment item's internal name to its descriptive header
    item_name_to_header_map = {item.name: f"{item.midterm}-{item.assessment_type}-{item.question_id}" for item in doc.assessment_structure}

    # Create the main data map: {student: {descriptive_header: marks}}
    # e.g., {'EDU-STU-001': {'Mid-1-Objective-Q1': 2.0, ...}}
    marks_map = {}
    for mark in raw_marks:
        student_name = mark.get("student")
        item_name = mark.get("assessment_item")
        marks = mark.get("marks_obtained")

        if student_name not in marks_map:
            marks_map[student_name] = {}
        
        descriptive_header = item_name_to_header_map.get(item_name)
        if descriptive_header:
            marks_map[student_name][descriptive_header] = marks

    # --- Step 4: Build the Final Report Rows ---
    data = []
    # Loop through the definitive student list from the summary table
    for student_summary in doc.final_scores_summary:
        row = {
            "register_number": student_summary.customer_student_id,
            "student_name": student_summary.student_name,
        }

        student_marks = marks_map.get(student_summary.student, {})
        
        # Loop through our dynamically created columns and fill in the marks
        for header, fieldname in column_header_to_fieldname.items():
            row[fieldname] = student_marks.get(header, 0)
        
        data.append(row)

    return columns, data