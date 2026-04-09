# Internal Assessments Module Documentation

## Overview
The `internal_assessments` module is a custom Frappe module designed to manage and calculate internal assessment marks for students. It supports two distinct workflows:
1.  **Granular Entry**: Capturing marks for every single question (Objective, Subjective, Assignment).
2.  **Manual Entry**: Directly entering the total marks for Mid-1 and Mid-2.

The system is designed to enforce data integrity while providing flexibility for instructors during the busy semester.

## Core DocType: Semester Midterm Assessment
The primary document is **Semester Midterm Assessment**. It links a **Student Group**, **Course**, and **Instructor** to a set of assessment marks.

### Data Model

The DocType consists of three main child tables and a control field:

#### 1. Control Fields
*   **`manual_entry_mode` (Check)**: A toggle that determines the source of truth for the marks.
    *   **Unchecked (Default)**: The system calculates totals by summing up individual questions. Manual edits to totals are overwritten.
    *   **Checked**: The system allows manual entry of totals. Question-level data is ignored for the total calculation.

#### 2. Assessment Structure (`assessment_structure`)
*   **Purpose**: Defines the schema of the assessment. It lists every single question or assessment item that will be graded.
*   **Fields**:
    *   `midterm`: The exam phase (e.g., "Mid-1", "Mid-2").
    *   `assessment_type`: The category (e.g., "Objective", "Subjective", "Assignment").
    *   `question_id`: A unique identifier for the question (e.g., "M1-Obj-Q1").
    *   `max_marks`: The maximum score possible for this item.
    *   `co_number`: The Course Outcome linked to this question.
*   **Automation**: The structure is often pre-filled by the `get_default_assessment_structure` function with a standard template.

#### 3. Student Marks Data (`student_marks_data`)
*   **Purpose**: Stores the raw, granular marks for every student and every question.
*   **Visibility**: This table is typically **hidden** from the UI to avoid clutter.
*   **Fields**:
    *   `student`: Link to the Student.
    *   `assessment_item`: Link to the specific row in the `Assessment Structure`.
    *   `marks_obtained`: The actual score given (stored as 0 if absent).
    *   `is_absent` (Check): Set to 1 when the student was absent for this question. Stored separately from `marks_obtained` so absent can be distinguished from a genuine score of zero.

#### 4. Final Scores Summary (`final_scores_summary`)
*   **Purpose**: Displays the calculated totals for the user. This is what the faculty sees.
*   **Fields**:
    *   `student`: Link to the Student.
    *   `mid_1_total`: Sum of all marks tagged as "Mid-1" (or manually entered). Stored as 0 if absent.
    *   `mid_1_absent` (Check): Set to 1 if the student was absent for the entire Mid-1 (i.e. all Mid-1 question rows are marked absent in Standard Mode, or "A" was entered in the Mid-1 Total column in Manual Mode).
    *   `mid_2_total`: Sum of all marks tagged as "Mid-2" (or manually entered). Stored as 0 if absent.
    *   `mid_2_absent` (Check): Same as `mid_1_absent` but for Mid-2.
    *   `total_internal_marks`: The final calculated score based on the logic described below.

---

## Key Logic & Workflows

### 1. Score Calculation (`recalculate_scores`)
This function is triggered on `before_save`. It employs a "Smart Fallback" logic based on the `manual_entry_mode` toggle.

#### Logic Flow:
1.  **Check Mode**:
    *   **If Manual Mode is OFF**: The system iterates through `student_marks_data`, sums up the marks for each student per midterm, and **overwrites** the `mid_1_total` and `mid_2_total` fields in the summary table. This enforces strict consistency between the breakdown and the total.
    *   **If Manual Mode is ON**: The system **skips** the summation step. It preserves whatever values are currently in the `mid_1_total` and `mid_2_total` fields (which the user likely typed manually).

2.  **Final Formula (Always Runs)**:
    *   Regardless of the mode, the system calculates the final internal mark using the standard university formula:
    *   `Best_Midterm = Max(Mid1, Mid2)`
    *   `Other_Midterm = Min(Mid1, Mid2)`
    *   `Final Marks = Round((0.8 * Best_Midterm) + (0.2 * Other_Midterm))`

### 2. UI/UX Behavior (Client Script)
*   **Column Locking**: A client script listens for changes to `manual_entry_mode`.
    *   When **ON**: The `Mid-1 Total` and `Mid-2 Total` columns are unlocked (Editable).
    *   When **OFF**: The columns are locked (Read-Only) to prevent misleading manual edits that would be overwritten on save.

### 3. Absent Marking
Students can be marked absent by entering `A` (case-insensitive) in any Excel cell instead of a numeric score.

*   **How it works**: The `parse_marks()` helper function intercepts any non-numeric cell value and returns `(0, is_absent=True)`. The numeric value stored in the DB is always `0`; the absent flag is stored separately.
*   **Standard Mode**: If `A` is entered for every question in a midterm, `recalculate_scores()` sets `mid_1_absent` or `mid_2_absent = 1` on the summary row. If even one question has a numeric score, the absent flag is not set.
*   **Manual Mode**: If `A` is entered in the "Mid-1 Total" or "Mid-2 Total" column, the corresponding absent flag is set directly on the summary row.
*   **Report**: The `Semester Midterm Assessment Report` displays `A` in any cell where the absent flag is set, and numeric values everywhere else. This distinguishes a genuine score of zero from an absent.
*   **Formula**: Absent is treated as 0 for the final marks calculation (`0.8 * Best + 0.2 * Other`).

### 4. Excel Integration
The module relies on Excel for bulk data entry of granular marks.

*   **Template Generation**: Creates an Excel file with columns for every item in the `Assessment Structure`.
*   **Upload Process**:
    *   Parses the uploaded Excel file.
    *   Cells containing `A` (or any non-numeric value) are treated as absent — stored as `marks_obtained = 0` with `is_absent = 1`.
    *   Populates the `student_marks_data` table.
    *   **Note**: If you upload an Excel sheet while in "Manual Mode", the granular data will be saved in the background, but the Totals will **not** update until you turn "Manual Mode" **OFF** and save.

---

## Technical Reference

### File Locations
*   **Controller**: `.../internal_assessments/doctype/semester_midterm_assessment/semester_midterm_assessment.py`
*   **Client Script**: `.../internal_assessments/doctype/semester_midterm_assessment/semester_midterm_assessment.js` (or similar path in `public/js`)

### Key Python Functions
*   `get_default_assessment_structure()`: Returns the hardcoded list of default questions.
*   `parse_marks(value)`: Module-level helper. Converts any cell value to `(float, is_absent)`. Non-numeric values (e.g. `"A"`) return `(0, True)`.
*   `recalculate_scores(self)`: The main logic engine. Contains the conditional logic for Manual vs. Automatic calculation. Also propagates `mid_1_absent`/`mid_2_absent` flags to the summary table.
*   `upload_marksheet(file_url, docname)`: Handles the parsing of the Excel file and data mapping. Uses `parse_marks()` to handle absent cells.

---

## Testing Scenarios & FAQ

### 1. Data Preservation (Manual vs. Standard)
**Q: If I have granular data, then enable Manual Mode and override a student's total, what happens to the granular data?**
*   **Answer**: The granular data (individual question marks) remains **unchanged** in the database. It is simply ignored for the calculation while Manual Mode is active.
*   **Implication**: If you later turn Manual Mode **OFF**, the system will revert to calculating the total from those preserved granular marks, effectively "undoing" your manual override.

### 2. Bulk Upload Behavior
*   **Scenario A: Standard Upload**
    *   **Action**: Upload a sheet with question columns (Manual Mode OFF).
    *   **Result**: The system **clears** all previous granular data and replaces it with the new upload. Totals are recalculated from these new marks.
*   **Scenario B: Manual Upload**
    *   **Action**: Upload a sheet with "Mid-1 Total" and "Mid-2 Total" columns (Manual Mode ON).
    *   **Result**: The system updates the totals in the summary table. Crucially, it **preserves** any existing granular data in the background.

### 3. Template Generation
*   **Rule**: To get the correct Excel template, you must set the toggle **before** clicking "Generate Marksheet Template".
    *   **Manual Mode ON** -> Downloads sheet with Total columns.
    *   **Manual Mode OFF** -> Downloads sheet with Question columns.

### 4. Recalculate Scores Button
*   **Purpose**: To provide an explicit, manual trigger for the calculation logic.
*   **Behavior**:
    *   Clicking this button forces the system to run `recalculate_scores()` immediately.
    *   For this to work we have to save the doc first and make sure it in draft state.
    *   It respects the current state of the `manual_entry_mode` toggle.
    *   Useful if you suspect the totals are out of sync or if you want to force a refresh after toggling modes without editing any fields.
