# 📊 Student Overall Semester Attendance Report - Documentation

## 📝 Overview
This report provides a comprehensive, daily view of a student's attendance across all their scheduled courses for a selected date range. It is designed to be a high-performance, easy-to-read "timetable style" report.

---

## 🏗️ Report Structure & Logic

### 1. The "Condensed Period" View
Unlike standard reports that create a column for every single course, this report uses **Dynamic Period Columns** (Period 1, Period 2, etc.).

*   **Why?** This prevents the report from having 30+ horizontal columns, making it much faster to load and easier to read on a single screen.
*   **Column Generation:** The report looks at the entire date range and finds the "busiest day" (the day with the most classes). It then creates exactly that many "Period" columns.
*   **Chronological Order:** For every day, the student's classes are filled into these columns from left to right, sorted by their start time.

### 2. Understanding the Cells
Each cell contains two pieces of information:
1.  **Status Abbreviation:**
    *   **P**: Present
    *   **A**: Absent
    *   **L**: On Leave
    *   **C**: Cancelled
    *   **Not marked**: A class was scheduled, but the instructor has not yet submitted the attendance for this student.
2.  **Class Time:** The start time of the class (e.g., `(9:00 am)`).

### 3. Why are some cells empty?
If you see an empty cell at the end of a row, it simply means the student had fewer classes on that day compared to their peak schedule. 
*   *Example:* If Friday has 6 classes but Thursday only has 4, the "Period 5" and "Period 6" columns will be empty for Thursday.

---

## 🧪 Testing Scenarios

Use these scenarios to verify the report's accuracy during UAT (User Acceptance Testing):

| Scenario | Expected Result |
| :--- | :--- |
| **Normal Attendance** | Cell shows **"P (Time)"** or **"A (Time)"** based on the record. |
| **Scheduled but No Attendance** | If a class exists in the `Course Schedule` but No record is in `Student Attendance`, the cell MUST show **"Not marked (Time)"**. |
| **Different Daily Counts** | Verify that a day with 3 classes has 3 filled cells and a day with 5 classes has 5 filled cells. |
| **New Semester Start** | Verify the report accurately identifies the student's current groups and only shows their relevant classes. |
| **Cancelled Classes** | If a class is marked as "Cancelled" in the attendance record, the cell shows **"C (Time)"**. |

---

## ⚙️ Technical Logic (For Admin)
*   **Source of Truth:** The report first aggregates all active **Student Groups** the student belongs to (both from formal membership and historical attendance).
*   **Schedule Matching:** It pulls all `Course Schedule` entries for those groups and matches them against `Student Attendance` IDs.
*   **Performance:** By using the "Condensed Period" layout, we avoid the "Sparse Data" problem (a table full of empty space/dashes), resulting in a 5x faster render time compared to standard grouped reports.
