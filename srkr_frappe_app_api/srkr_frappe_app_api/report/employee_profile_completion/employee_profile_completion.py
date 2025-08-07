import frappe
from frappe import _

# List of fields to IGNORE by their name
FIELDS_TO_IGNORE = [
    "naming_series", "amended_from", "image", "sb", "salutation",
    "doctype", "owner", "creation", "modified", "modified_by",
    "docstatus", "parent", "parentfield", "parenttype", "idx",
    "_user_tags", "_comments", "_assign", "_liked_by",
    "user_id", "attendance_device_id", "holiday_list", "default_shift",
    "payroll_cost_center", "expense_approver", "leave_approver", "shift_request_approver",
    "employee_name", "first_name", "middle_name", "last_name", "reports_to_name",
]

# NEW: List of field TYPES to IGNORE.
# This will remove all layout-related fields from the report.
FIELDTYPES_TO_IGNORE = [
    "Section Break",
    "Column Break",
    "Tab Break",
    "HTML",
    "Read Only",
    "Button"
]

def execute(filters=None):
    columns, fields_to_check = get_columns_and_fields()
    if not columns:
        return [], []
        
    data = get_data(filters, fields_to_check)
    
    message = _("Green = Filled, Red = Not Filled")
    
    return columns, data, message

def get_columns_and_fields():
    """Dynamically generate columns, ignoring layout and system fields."""
    columns = [
        {"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Link", "options": "Employee", "width": 200},
        {"fieldname": "completion_percentage", "label": _("Profile Completion"), "fieldtype": "Percent", "width": 150}
    ]

    fields_to_check = []
    meta = frappe.get_meta("Employee")

    for field in meta.fields:
        # UPDATED LOGIC: Now checks both the name and the type against our ignore lists.
        if field.fieldname not in FIELDS_TO_IGNORE and field.fieldtype not in FIELDTYPES_TO_IGNORE:
            fields_to_check.append(field.fieldname)
            
            label = field.label or field.fieldname.replace("_", " ").title()
            columns.append({
                "fieldname": field.fieldname,
                "label": _(label),
                "fieldtype": "Data",
                "width": 180
            })

    return columns, fields_to_check

def get_data(filters, fields_to_check):
    """Fetch employees and check each specified field for completeness."""
    
    conditions = {"status": "Active"}
    if filters and filters.get("employee"):
        conditions["name"] = filters.get("employee")

    employee_names = frappe.get_all("Employee", filters=conditions, pluck="name")

    final_data = []
    total_fields_to_check = len(fields_to_check)

    for name in employee_names:
        doc = frappe.get_doc("Employee", name)
        
        row = { "employee_name": doc.employee_name }
        filled_count = 0
        
        for fieldname in fields_to_check:
            value = doc.get(fieldname)
            is_filled = False
            
            if isinstance(value, list):
                if len(value) > 0:
                    is_filled = True
            elif value:
                is_filled = True

            if is_filled:
                row[fieldname] = "Filled"
                filled_count += 1
            else:
                row[fieldname] = "Not Filled"
        
        if total_fields_to_check > 0:
            percentage = round((filled_count / total_fields_to_check) * 100, 2)
            row["completion_percentage"] = percentage
        else:
            row["completion_percentage"] = 0
        
        final_data.append(row)

    return final_data