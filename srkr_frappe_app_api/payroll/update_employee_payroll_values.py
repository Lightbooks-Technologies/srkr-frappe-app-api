"""
Update script: Populate payroll custom field values on Employee records from CSV.

CSV file: Update1_Employee_CustomFields.csv
Fields updated: da_percent, hra_percent, esi_eligible

Usage (bench console):
    Paste the setup() call after importing, or run via bench execute:
    bench --site <site-name> execute srkr_frappe_app_api.payroll.update_employee_payroll_values.setup
    bench --site <site-name> execute srkr_frappe_app_api.payroll.update_employee_payroll_values.rollback
"""

import csv
import os

import frappe

CSV_FILE = os.path.join(os.path.dirname(__file__), "Update1_Employee_CustomFields.csv")

FIELDS = ["da_percent", "hra_percent", "esi_eligible"]


def _load_csv():
    with open(CSV_FILE, newline="") as f:
        return list(csv.DictReader(f))


def setup():
    rows = _load_csv()

    updated, skipped = [], []

    for row in rows:
        employee_id = row["ID"].strip()

        if not frappe.db.exists("Employee", employee_id):
            skipped.append(employee_id)
            continue

        frappe.db.set_value(
            "Employee",
            employee_id,
            {
                "da_percent": round(float(row["da_percent"]), 4),
                "hra_percent": round(float(row["hra_percent"]), 4),
                "esi_eligible": int(row["esi_eligible"]),
            },
            update_modified=False,
        )
        updated.append(employee_id)

    frappe.db.commit()

    print(f"Updated : {len(updated)} employee(s)")
    if skipped:
        print(f"Skipped (not found): {len(skipped)} — {skipped}")


def rollback():
    """Reset the three fields to their defaults for all employees in the CSV."""
    rows = _load_csv()

    reset, skipped = [], []

    for row in rows:
        employee_id = row["ID"].strip()

        if not frappe.db.exists("Employee", employee_id):
            skipped.append(employee_id)
            continue

        frappe.db.set_value(
            "Employee",
            employee_id,
            {
                "da_percent": 0.0,
                "hra_percent": 0.0,
                "esi_eligible": 0,
            },
            update_modified=False,
        )
        reset.append(employee_id)

    frappe.db.commit()

    print(f"Reset : {len(reset)} employee(s)")
    if skipped:
        print(f"Skipped (not found): {len(skipped)} — {skipped}")
