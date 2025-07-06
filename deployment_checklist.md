# Exam Results Sync - Deployment Checklist

This checklist ensures a smooth deployment of the exam results sync feature.

## Files Updated/Created

- [x] DocType JSON files:
  - `srkr_frappe_app_api/doctype/subject_result/subject_result.json`
  - `srkr_frappe_app_api/doctype/semester_result/semester_result.json`

- [x] Backend Integration:
  - `srkr_frappe_app_api/api.py` - Contains the `sync_student_results` function

- [x] UI Integration:
  - `srkr_frappe_app_api/public/js/student.js` - Adds "Sync Exam Results" button to Student form
  - `srkr_frappe_app_api/hooks.py` - Links the client script to the Student DocType

- [x] Documentation:
  - `exam_results_sync_guide.md` - Implementation guide

- [x] Security Script (to be added via UI after deployment):
  - Server script to make Semester Results read-only

## Deployment Steps

1. **Cleanup** (if running on a test/development site with previous attempts):
   ```bash
   bench --site srkr.lightbooks-dev.io console
   ```
   
   Run this in the console:
   ```python
   print("--- Deleting DocTypes to prepare for file-based creation ---")
   frappe.delete_doc("DocType", "Semester Result", ignore_missing=True, force=True)
   frappe.delete_doc("DocType", "Subject Result", ignore_missing=True, force=True)
   frappe.db.commit()
   print("--- Cleanup Finished ---")
   exit()
   ```

2. **Update Code**:
   ```bash
   cd /path/to/bench
   git -C apps/srkr-frappe-app-api pull  # If using git
   # Or manually update the files
   ```

3. **Run Migration**:
   ```bash
   bench --site srkr.lightbooks-dev.io migrate
   ```

4. **Restart the Server**:
   ```bash
   bench restart
   ```

5. **Add Server Script** for security (via UI):
   - Go to "Server Script List" > "Add Server Script"
   - Script Name: "Prevent Semester Result Edit"
   - Script Type: "DocType Event"
   - Reference DocType: "Semester Result"
   - DocType Event: "Before Save"
   - Script:
     ```python
     # Allow creation, but block any future saves.
     if not doc.is_new():
         frappe.throw("Official Semester Results are read-only and cannot be modified.")
     ```
   - Check "Enabled" and Save

6. **Configure API Key**:
   - Make sure the SRKR API key is set in `site_config.json`:
   ```bash
   bench --site srkr.lightbooks-dev.io set-config srkr_api_key "your-api-key-here"
   ```

7. **Test the Integration**:
   - Open a Student record with a hall ticket number
   - Click the "Sync Exam Results" button
   - Verify that results are fetched and stored correctly

## API Endpoint Reference

The external API endpoint used is:
```
https://api.srkrexams.in/api/Result/GetResultByRegNo
```

Parameters:
- `regNo`: Student's hall ticket number
- `sSEM`: "ALL" to fetch all semester results

Headers:
- `x-api-key`: API key for authentication

## Troubleshooting

If issues arise during deployment:

1. Check error logs:
   ```bash
   bench --site srkr.lightbooks-dev.io show-logs
   ```

2. Verify DocTypes exist:
   ```bash
   bench --site srkr.lightbooks-dev.io console
   ```
   Then in the console:
   ```python
   frappe.db.exists("DocType", "Subject Result")
   frappe.db.exists("DocType", "Semester Result")
   ```

3. Test API connectivity:
   ```python
   import requests
   api_key = frappe.conf.get("srkr_api_key")
   headers = {"x-api-key": api_key}
   response = requests.get("https://api.srkrexams.in/api/Result/GetResultByRegNo", 
                         params={"regNo": "test_reg_no", "sSEM": "ALL"}, 
                         headers=headers)
   print(response.status_code)
   ```

4. Re-run the manual import script if needed:
   ```bash
   bench --site srkr.lightbooks-dev.io execute import_doctypes_manually.py
   ```
