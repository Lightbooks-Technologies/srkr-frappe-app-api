# Server Script: Prevent Semester Result Edit
#
# This script prevents editing of Semester Result documents after they've been created
# to ensure data integrity of official results.
#
# DocType Event: Before Save
# Reference DocType: Semester Result

# Allow creation, but block any future saves.
if not doc.is_new():
    frappe.throw("Official Semester Results are read-only and cannot be modified.")
