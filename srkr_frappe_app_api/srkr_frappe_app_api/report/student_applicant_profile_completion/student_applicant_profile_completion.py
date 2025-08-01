import frappe
from frappe import _

# The full list of fields to include in the report
FIELDS_TO_CHECK = [
    # Original fields showing value
    "custom_name_as_per_ssc",
    "custom_hall_ticket_number",
    "student_mobile_number",
    # NEW fields to show value
    "custom_cet_type",
    "custom_admission_quota",
    "custom_admission_type",
    "program",
    "custom_rank",
    "custom_scholarship_eligible",
    # Fields showing status
    "custom_allotment_letter",
    "custom_10th_certificate",
    "custom_12th_certificate",
    "custom_previous_degree_certificate",
    "custom_transfer_certificate",
    "custom_study_certificate",
    "custom_caste_certificate",
    "custom_parents_income_proof",
    "custom_aadhaar_card",
    "custom_fathers_id_proof",
    "custom_mothers_id_proof",
    "custom_ration_or_rice_card",
    "custom_passbook_proof",
    "custom_ward_sachivalayam_centre_name",
    "custom_ward_sachivalayam_centre_code_no"
]

# List of fields for which we want to display the actual value
FIELDS_TO_SHOW_VALUE = [
    # Original fields
    "custom_name_as_per_ssc",
    "custom_hall_ticket_number",
    "student_mobile_number",
    # NEW FIELDS ADDED HERE
    "custom_cet_type",
    "custom_admission_quota",
    "custom_admission_type",
    "program",
    "custom_rank",
    "custom_scholarship_eligible",
]

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    message = _("Green = Filled, Red = Not Filled")
    
    return columns, data, message

def get_columns():
    """Generate columns ONLY from the predefined FIELDS_TO_CHECK list."""
    columns = [
        {"fieldname": "applicant_name", "label": _("Student Applicant ID"), "fieldtype": "Link", "options": "Student Applicant", "width": 200}
    ]

    meta = frappe.get_meta("Student Applicant")
    meta_fields_dict = {f.fieldname: f for f in meta.fields}

    for fieldname in FIELDS_TO_CHECK:
        field = meta_fields_dict.get(fieldname)
        
        if field:
            label = field.label or field.fieldname.replace("_", " ").title()
            columns.append({
                "fieldname": fieldname,
                "label": _(label),
                "fieldtype": "Data",
                "width": 180
            })

    return columns

def get_data(filters):
    """Fetch applicants and check fields, showing actual values for specified fields."""
    
    conditions = {}
    if filters and filters.get("student_applicant"):
        conditions["name"] = filters.get("student_applicant")

    fields_to_fetch = ["name"] + FIELDS_TO_CHECK
    applicant_docs = frappe.get_list("Student Applicant", filters=conditions, fields=fields_to_fetch)

    final_data = []
    for doc in applicant_docs:
        row = { "applicant_name": doc.name }
        
        for fieldname in FIELDS_TO_CHECK:
            value = doc.get(fieldname)
            
            if fieldname in FIELDS_TO_SHOW_VALUE:
                if value:
                    row[fieldname] = value
                else:
                    row[fieldname] = "Not Filled"
            else:
                if value:
                    row[fieldname] = "Filled"
                else:
                    row[fieldname] = "Not Filled"
        
        final_data.append(row)

    return final_data