# Student Cumulative Attendance Report - Logic Explanation

This document explains how the "Total Classes" column is calculated and the recent changes made to fix the issue where the count was appearing too high.

## Core Logic Flow

The report uses a multi-step process to ensure that the "Total Classes" count reflects all subjects a student is enrolled in, not just the ones under the selected Student Group.

1.  **Selection**: You select a **Student Group** (the "Anchor Group").
2.  **Context Extraction**: The report looks up the `Academic Year` and `Academic Term` associated with that Anchor Group.
3.  **Sibling Groups**: It finds all other Student Groups in the system that share the same `Academic Year` and `Academic Term`.
4.  **Student Enrollment**: It identifies the students belonging to the Anchor Group.
5.  **Multi-Group Mapping**: For each of those students, it calculates which of the "Sibling Groups" they are active members of (e.g., Lab groups, Elective groups, or Section groups).
6.  **Schedule Aggregation**: It gathers all unique `Course Schedule` entries across all those mapped groups to produce the `Total Classes` count.

## Why "Total Classes" was too high

Previously, the report was counting every single `Course Schedule` record found in the database for those groups, which caused three major issues:
- **Future Classes**: It included classes scheduled for future dates (e.g., until the end of the semester).
- **No-Show Classes**: It included scheduled classes where attendance was never actually taken or submitted.
- **Term Overlap**: If the `Academic Term` was not strictly defined, it could pull in classes from multiple semesters.

## Recent Fixes

We modified the logic in `student_cumulative_attendance.py` to make the count more accurate:

### 1. Attendance Submission Check
The report now joins the `Course Schedule` table with the `Student Attendance` table. A class is only counted if it has at least one **submitted** attendance record (`docstatus = 1`).
*   *Benefit:* Classes that were cancelled or where attendance wasn't recorded are no longer counted in the denominator.

### 2. Date Boundary (Today's Date)
We added a filter to only include classes where the `schedule_date` is **less than or equal to today**.
*   *Benefit:* Future classes that haven't happened yet are excluded from the "Total Classes" count.

### 3. First-Year Logic
For first-year groups (identified by patterns like `SEM-01`), the report respects a specific start date (`FIRST_YEAR_ATTENDANCE_START_DATE`) to avoid including orientation or early-term data from before the official start.

## Technical Implementation (SQL/Query Builder)

The updated query for fetching schedules looks like this:

```python
schedules_query = (
    frappe.qb.from_(CourseSchedule)
    .join(StudentAttendance).on(StudentAttendance.course_schedule == CourseSchedule.name)
    .select(CourseSchedule.name, CourseSchedule.student_group)
    .where(CourseSchedule.student_group.isin(semester_student_groups))
    .where(StudentAttendance.docstatus == 1)
    .where(CourseSchedule.schedule_date <= frappe.utils.today())
)
```

## Maintenance Tips
- **Keep Terms Updated**: Ensure every `Student Group` has the correct `Academic Term` assigned. If the term is blank, the report may still pull in classes from the entire academic year.
- **Configuration**: You can adjust the `FIRST_YEAR_ATTENDANCE_START_DATE` at the top of the `.py` file if the start date for 1st-year students changes.
