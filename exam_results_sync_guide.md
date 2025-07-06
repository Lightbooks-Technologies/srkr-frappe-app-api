# SRKR Exam Results Sync - Implementation Guide

This document provides an overview of the exam results sync feature implementation in the SRKR Frappe App API.

## Feature Overview

The exam results sync feature allows administrators and students to:

1. Fetch exam results from the external SRKR API
2. Store results in structured DocTypes within Frappe
3. View semester-wise performance and subject details
4. Access historical exam data for reference

## API Integration

### API Endpoint
The system integrates with the external API at:
```
https://api.srkrexams.in/api/Result/GetResultByRegNo
```

### Authentication
- The API requires an API key for authentication, stored in `site_config.json` as `srkr_api_key`
- The key is passed in the request header as `x-api-key`

### Parameters
- `regNo`: The student's hall ticket number (stored in `custom_hall_ticket_number` field in Student DocType)
- `sSEM`: Set to "ALL" to fetch all semester results

## DocType Structure

Two main DocTypes are used to store the exam results:

1. **Semester Result**
   - Parent DocType that stores semester-level data like SGPA, CGPA
   - Each record represents one semester's results for a student
   - Named automatically as "SR-{student}-{semester}"
   - Read-only after creation (enforced by server script)

2. **Subject Result**
   - Child table DocType linked to Semester Result
   - Stores subject-level details like grade, credits, result status
   - Multiple subject results are linked to a single semester result

## User Experience

1. Navigate to a Student record in Frappe
2. Click the "Sync Exam Results" button
3. The system fetches data from the API and creates/updates Semester Result records
4. Success message shows how many semesters were synced

## Error Handling

The implementation includes robust error handling for:
- Missing hall ticket numbers
- API connection failures
- Missing configuration (API key)
- Data validation issues
- Failed semester mappings

## Adding New Students

For new students to use this feature:
1. Create a Student record in Frappe
2. Add the student's hall ticket number in the `custom_hall_ticket_number` field
3. Save the record
4. The "Sync Exam Results" button will appear on the form

## Server-side Security

A server script ensures that once created, Semester Result records cannot be modified, preserving the integrity of official results.

## Troubleshooting

If the sync feature isn't working:

1. Check that the `srkr_api_key` is correctly set in `site_config.json`
2. Verify the student has a valid hall ticket number
3. Ensure the Semester DocTypes exist in the system with correct semester numbers
4. Check the error logs for detailed error messages
