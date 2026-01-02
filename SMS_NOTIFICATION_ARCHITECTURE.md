# SMS Notification Architecture & Scaling Guide

This document explains the architecture of the **SMS Notification Settings** system within the `srkr_frappe_app_api` app. Use this guide to help an LLM or developer add new UI-configurable SMS jobs.

## 1. Overview
The system uses a **Single DocType** named `SMS Notification Settings` to provide a no-code UI for administrators. The Python functions in `api.py` read these settings at runtime to decide whether to trigger and how to filter notifications.

## 2. DocType Details
- **DocType Name**: `SMS Notification Settings`
- **Type**: Single (Only one record exists)
- **Module**: `srkr_frappe_app_api`

### Current Fields:
- `dry_run` (Check): Global toggle. If enabled, no SMS is actually sent; messages are only printed to logs.
- `enable_daily_summary` (Check): Master toggle for the Daily summary job.
- `daily_summary_category` (Data): The program prefix (e.g., `BTECH`).
- `sem_01` to `sem_08` (Check): Checkbox for each semester.

## 3. How to Add a New SMS Job (e.g., Instructor Reminders)

### Step A: Update the DocType UI
Add new fields to the `SMS Notification Settings` DocType via the JSON file or Frappe Desk:
1. Add a **Section Break** named "Instructor Reminders".
2. Add a `Check` field: `enable_instructor_reminders`.
3. Add any filter fields (e.g., `reminder_semesters`).

### Step B: Update the Python Logic
In `instructor/api.py`, update your function to fetch these settings:

```python
def send_instructor_reminders():
    # 1. Fetch settings record
    settings = frappe.get_single("SMS Notification Settings")
    
    # 2. Check Master Switch
    if not settings.enable_instructor_reminders:
        return
    
    # 3. Fetch Dynamic Filters
    active_sems = []
    for i in range(1, 9):
        if settings.get(f"sem_0{i}"): # reuse existing semester toggles or add new ones
            active_sems.append(f"SEM-0{i}")
            
    # ... rest of your logic ...
```

### Step C: Use the SMS Helper
Always use the `send_summary_sms_helper` function. It automatically respects the `dry_run` setting:

```python
message_id = send_summary_sms_helper(mobile_no, message_text, template_id)
```

## 4. Testing without sending SMS
1. Go to **SMS Notification Settings**.
2. Check **Dry Run (Log Only - No SMS)**.
3. Save.
4. Run your function manually or via console.
5. Check the bench console or logs for: `[DRY RUN] Would send to ...`

---
*Created on 2026-01-02*
