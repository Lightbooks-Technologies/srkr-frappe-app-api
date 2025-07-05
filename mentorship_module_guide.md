# SRKR Mentorship Module Integration Guide

## Overview

The Mentorship Module is a comprehensive solution for tracking student progress, managing mentor-student relationships, and providing a live academic dashboard to mentors. This module fully integrates with the Exam Results feature we recently developed, providing a unified view of student performance.

## Features

1. **Student Mentorship Profiles**
   - Centralized student profile with academic performance data
   - Goal planning and tracking
   - Co-curricular activities log

2. **Live Academic Dashboard**
   - Current term course attendance
   - Complete exam results history
   - Semester-wise SGPA and CGPA tracking

3. **Mentorship Log Entries**
   - Record detailed mentorship sessions
   - Track academic feedback
   - Document campus life experiences
   - Set action plans for improvement

## Integration with Exam Results

The Mentorship Module seamlessly integrates with the Exam Results feature by:

1. Pulling live data from the Semester Results and Subject Results DocTypes
2. Displaying a student's complete academic history
3. Highlighting current academic standing
4. Identifying subjects where students are struggling

## Installation and Setup

### Prerequisites

- ERPNext Education module must be installed and configured
- The Exam Results feature should be set up (as we've already done)

### Setup Process

1. **Run the Setup Script**:
   ```bash
   cd /path/to/frappe-bench
   bench --site your-site-name console
   ```

   Then in the console:
   ```python
   import sys
   sys.path.append('/path/to/frappe-bench/apps/srkr-frappe-app-api')
   import setup_mentorship_module
   setup_mentorship_module.run_complete_mentorship_setup()
   ```

2. **Apply Migrations**:
   After exiting the console, run:
   ```bash
   bench migrate
   bench restart
   ```

3. **Verify Installation**:
   - Navigate to "Education" module in your Frappe Desk
   - Check for the "Student Mentorship Profile" and "Mentorship Log Entry" DocTypes
   - Open a Student Mentorship Profile to see the live academic dashboard

## Using the Mentorship Module

### For Administrators

1. **Assign Mentors**:
   - Open a Student Mentorship Profile
   - Set the "Current Mentor" field to the appropriate Instructor
   - Submit the profile

2. **Monitor Mentorship Activity**:
   - Review Mentorship Log entries
   - Track goal completion rates

### For Mentors

1. **View Student Dashboard**:
   - Open a Student Mentorship Profile
   - Navigate to the "Live Dashboard" tab
   - View current attendance and exam results

2. **Record Mentorship Sessions**:
   - Click "Add Mentorship Log" button from a Student Mentorship Profile
   - Fill in the session details
   - Set action items for follow-up

3. **Track Student Goals**:
   - Add term goals in the "Goal Plan" tab
   - Update goal status as the student progresses

## Troubleshooting

If the academic dashboard shows an error or doesn't load:

1. **Check API Access**:
   - Ensure the user has proper permissions to access student data
   - Verify that the Semester Result and Subject Result DocTypes exist

2. **Verify Data**:
   - Confirm that the student has a valid Program Enrollment
   - Check that Course Enrollments exist for the current term
   - Ensure Semester Results have been synced using the "Sync Exam Results" button

3. **Review Server Logs**:
   - Check the `bench.log` file for any API errors
   - Look for "Mentorship Dashboard Error" entries

## Best Practices

1. **Regular Updates**:
   - Sync exam results before mentorship sessions
   - Update attendance records regularly

2. **Comprehensive Documentation**:
   - Log all mentorship sessions
   - Document student concerns thoroughly
   - Set clear action items with timelines

3. **Data Privacy**:
   - Only share student profiles with authorized personnel
   - Use the permissions system to restrict access to sensitive information

## Technical Information

The module consists of the following components:

1. **DocTypes**:
   - Student Mentorship Profile
   - Mentorship Log Entry
   - Mentorship Goals (Child Table)
   - Mentorship Activities (Child Table)

2. **API Endpoints**:
   - `get_student_academic_summary`: Retrieves comprehensive academic data for a student

3. **Client Scripts**:
   - Dynamic dashboard rendering
   - Custom button for creating log entries

---

For technical support, please contact the development team.
