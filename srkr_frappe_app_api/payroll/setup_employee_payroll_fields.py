"""
Setup script: Add payroll custom fields to Employee DocType.

Usage:
    bench --site <site-name> execute setup_employee_payroll_fields.setup
    bench --site <site-name> execute setup_employee_payroll_fields.rollback

The setup function is idempotent — safe to run multiple times.
The rollback function removes only the fields this script created.
"""

import frappe

CUSTOM_FIELDS = [
    {
        "dt": "Employee",
        "fieldname": "srkr_payroll_section",
        "fieldtype": "Section Break",
        "label": "Payroll Settings",
        "insert_after": "bank_ac_no",
    },
    {
        "dt": "Employee",
        "fieldname": "da_percent",
        "fieldtype": "Float",
        "label": "DA Percent",
        "insert_after": "srkr_payroll_section",
        "description": "Dearness Allowance percentage",
    },
    {
        "dt": "Employee",
        "fieldname": "hra_percent",
        "fieldtype": "Float",
        "label": "HRA Percent",
        "insert_after": "da_percent",
        "description": "House Rent Allowance percentage",
    },
    {
        "dt": "Employee",
        "fieldname": "srkr_payroll_col_break",
        "fieldtype": "Column Break",
        "label": "",
        "insert_after": "hra_percent",
    },
    {
        "dt": "Employee",
        "fieldname": "esi_eligible",
        "fieldtype": "Check",
        "label": "ESI Eligible",
        "insert_after": "srkr_payroll_col_break",
    },
    {
        "dt": "Employee",
        "fieldname": "pay_scale_code",
        "fieldtype": "Data",
        "label": "Pay Scale Code",
        "insert_after": "esi_eligible",
    },
    {
        "dt": "Employee",
        "fieldname": "attendance_department",
        "fieldtype": "Link",
        "label": "Attendance Department",
        "options": "Department",
        "insert_after": "pay_scale_code",
        "description": "Department used for attendance marking (may differ from primary department)",
    },
]

# Fieldnames owned by this script — used by rollback to know what to delete.
# Includes the layout helpers (section break, column break) we inserted.
OWNED_FIELDNAMES = [cf["fieldname"] for cf in CUSTOM_FIELDS]


def setup():
    created = []
    skipped = []

    for cf in CUSTOM_FIELDS:
        fieldname = cf["fieldname"]
        dt = cf["dt"]

        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
            skipped.append(fieldname)
            continue

        doc = frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": dt,
                "fieldname": fieldname,
                "fieldtype": cf["fieldtype"],
                "label": cf.get("label", ""),
                "insert_after": cf.get("insert_after", ""),
                "options": cf.get("options", ""),
                "description": cf.get("description", ""),
            }
        )
        doc.insert(ignore_permissions=True)
        created.append(fieldname)

    frappe.db.commit()

    if created:
        print(f"Created {len(created)} field(s): {', '.join(created)}")
    if skipped:
        print(f"Skipped {len(skipped)} already-existing field(s): {', '.join(skipped)}")
    if not created and not skipped:
        print("Nothing to do.")


def rollback():
    deleted = []
    missing = []

    for fieldname in OWNED_FIELDNAMES:
        name = frappe.db.get_value("Custom Field", {"dt": "Employee", "fieldname": fieldname}, "name")
        if name:
            frappe.delete_doc("Custom Field", name, ignore_permissions=True)
            deleted.append(fieldname)
        else:
            missing.append(fieldname)

    frappe.db.commit()

    if deleted:
        print(f"Deleted {len(deleted)} field(s): {', '.join(deleted)}")
    if missing:
        print(f"Already absent — skipped {len(missing)} field(s): {', '.join(missing)}")
