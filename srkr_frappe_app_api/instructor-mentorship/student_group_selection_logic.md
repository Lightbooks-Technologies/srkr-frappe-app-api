# Student Group Selection Logic

## Problem Statement
In the mentorship API (`get_mentorship_students`), we currently fetch the student's group from the `Student Group Student` mapping table. However, when a student is promoted from one semester to another, they are often added to a new group but **not removed** from the old one. Both records remain marked as `active`, leading to:
1.  **Ambiguity:** The API picks an arbitrary group (often the old one).
2.  **Incorrect Data:** Attendance percentages are calculated based on historical schedules instead of current ones.

## Identification of Edge Cases

### 1. Semester Promotion (Multiple active terms)
A student might have "Enabled" group mappings for `SEM-03` and `SEM-04` simultaneously. Simply picking the first "active" record might return the stale semester.

### 2. Primary Group vs. Sub-Groups
Students are often mapped to multiple groups within the *same* semester:
*   **Batch (Primary):** The main section (e.g., "Section B").
*   **Activity (Sub-group):** Lab batches, electives, or remedial groups (e.g., "Batch B1").
The API should prioritize displaying the "Batch" group as the student's primary identity.

### 3. Future Preparation
Admin teams often create groups for the *next* semester (e.g., `SEM-05`) a few weeks before classes start. If we simply pick the "Highest Semester," the mentorship profile would switch to the next semester prematurely, while the student is still attending current classes.

### 4. Overlapping Academic Terms
During transition periods or supplementary exams, two academic terms might technically overlap for a few days. We need a deterministic "tie-breaker" to decide which one is currently in effect.

## Proposed Selection Logic (The "Latest Active" Rule)

To resolve these cases, the `get_mentorship_students` function should be updated to fetch groups using the following hierarchy:

### 1. Date Validation
Filter for groups where the linked `Academic Term`:
*   `Start Date <= Today`
*   This ensures we ignore "Future Prep" groups.

### 2. Primary Sort: Latest Start Date
Sort valid groups by `Academic Term Start Date` in **Descending** order.
*   **Benefit:** Resolves overlapping terms by always favoring the most recently started semester.

### 3. Secondary Sort: Group Type Priority
Within the same semester, sort by `Group Based On` with a priority mapping:
1.  `Batch` (Priority 1)
2.  `Activity` (Priority 2)
*   **Benefit:** Ensures "Section B" is shown instead of "Lab B1".

### 4. Fallback (Creation Date)
If all else is equal, use `creation desc` to pick the newest record.

## Implementation Strategy
Instead of fetching from `Student Group Student` directly, we will perform a **Join** with the `Student Group` and `Academic Term` doctypes to access the necessary dates and metadata for this selective logic.
