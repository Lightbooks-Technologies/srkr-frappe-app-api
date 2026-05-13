# Employee Payroll Custom Fields Setup

Adds 5 custom fields to the **Employee** doctype under the **Salary** tab.

| Field Label | Fieldname | Type |
|---|---|---|
| DA Percent | `da_percent` | Float |
| HRA Percent | `hra_percent` | Float |
| ESI Eligible | `esi_eligible` | Check |
| Pay Scale Code | `pay_scale_code` | Data |
| Attendance Department | `attendance_department` | Link → Department |

---

## Setup

```bash
bench --site <site-name> console
```

Paste:

```python
import frappe

CUSTOM_FIELDS = [
    {"dt": "Employee", "fieldname": "srkr_payroll_section", "fieldtype": "Section Break", "label": "Payroll Settings", "insert_after": "bank_ac_no"},
    {"dt": "Employee", "fieldname": "da_percent", "fieldtype": "Float", "label": "DA Percent", "insert_after": "srkr_payroll_section", "description": "Dearness Allowance percentage"},
    {"dt": "Employee", "fieldname": "hra_percent", "fieldtype": "Float", "label": "HRA Percent", "insert_after": "da_percent", "description": "House Rent Allowance percentage"},
    {"dt": "Employee", "fieldname": "srkr_payroll_col_break", "fieldtype": "Column Break", "label": "", "insert_after": "hra_percent"},
    {"dt": "Employee", "fieldname": "esi_eligible", "fieldtype": "Check", "label": "ESI Eligible", "insert_after": "srkr_payroll_col_break"},
    {"dt": "Employee", "fieldname": "pay_scale_code", "fieldtype": "Data", "label": "Pay Scale Code", "insert_after": "esi_eligible"},
    {"dt": "Employee", "fieldname": "attendance_department", "fieldtype": "Link", "label": "Attendance Department", "options": "Department", "insert_after": "pay_scale_code", "description": "Department used for attendance marking (may differ from primary department)"},
]

created, skipped = [], []
for cf in CUSTOM_FIELDS:
    if frappe.db.exists("Custom Field", {"dt": cf["dt"], "fieldname": cf["fieldname"]}):
        skipped.append(cf["fieldname"])
        continue
    frappe.get_doc({"doctype": "Custom Field", **cf}).insert(ignore_permissions=True)
    created.append(cf["fieldname"])

frappe.db.commit()
print(f"Created: {created}\nSkipped: {skipped}")
```

---

## Rollback

```bash
bench --site <site-name> console
```

Paste:

```python
OWNED = ["srkr_payroll_section", "da_percent", "hra_percent", "srkr_payroll_col_break", "esi_eligible", "pay_scale_code", "attendance_department"]

deleted, missing = [], []
for fieldname in OWNED:
    name = frappe.db.get_value("Custom Field", {"dt": "Employee", "fieldname": fieldname}, "name")
    if name:
        frappe.delete_doc("Custom Field", name, ignore_permissions=True)
        deleted.append(fieldname)
    else:
        missing.append(fieldname)

frappe.db.commit()
print(f"Deleted: {deleted}\nAlready absent: {missing}")
```

---

# Employee Payroll Values Update

Populates `da_percent`, `hra_percent`, `esi_eligible` on 562 Employee records from `Update1_Employee_CustomFields.csv`.

> Run **after** the custom fields setup above.

## Setup

```bash
bench --site <site-name> console
```

Paste:

```python
import csv, os, frappe

CSV_FILE = "/home/frappe/frappe-bench/apps/srkr_frappe_app_api/srkr_frappe_app_api/payroll/Update1_Employee_CustomFields.csv"

with open(CSV_FILE, newline="") as f:
    rows = list(csv.DictReader(f))

updated, skipped = [], []
for row in rows:
    emp = row["ID"].strip()
    if not frappe.db.exists("Employee", emp):
        skipped.append(emp)
        continue
    frappe.db.set_value("Employee", emp, {
        "da_percent": round(float(row["da_percent"]), 4),
        "hra_percent": round(float(row["hra_percent"]), 4),
        "esi_eligible": int(row["esi_eligible"]),
    }, update_modified=False)
    updated.append(emp)

frappe.db.commit()
print(f"Updated: {len(updated)}")
if skipped:
    print(f"Skipped (not found): {skipped}")
```

## Rollback

```python
import csv, frappe

CSV_FILE = "/home/frappe/frappe-bench/apps/srkr_frappe_app_api/srkr_frappe_app_api/payroll/Update1_Employee_CustomFields.csv"

with open(CSV_FILE, newline="") as f:
    rows = list(csv.DictReader(f))

reset, skipped = [], []
for row in rows:
    emp = row["ID"].strip()
    if not frappe.db.exists("Employee", emp):
        skipped.append(emp)
        continue
    frappe.db.set_value("Employee", emp, {
        "da_percent": 0.0,
        "hra_percent": 0.0,
        "esi_eligible": 0,
    }, update_modified=False)
    reset.append(emp)

frappe.db.commit()
print(f"Reset: {len(reset)}")
if skipped:
    print(f"Skipped (not found): {skipped}")
```
