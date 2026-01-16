# Database Interaction & Architecture Documentation

This document explicitly details how the CGPA System's web service (`app.py`) interacts with the SQLite database (`database.db`) for every major page and workflow.

---

## 1. Database Schema Overview
The system relies on a relational schema with the following key tables:

### Core Tables
- **`users`**: Stores student and admin identities.
    - *Columns*: `id`, `email`, `name`, `roll_number`, `enrollment_number` [NEW], `department` [NEW], `academic_year` [NEW], `current_year` [NEW], `is_admin`.
- **`presets`**: Defines class structures (e.g., "SE Computer Engineering Sem 3").
    - *Columns*: `id`, `academic_year`, `course`, `department` [NEW], `year`, `division`, `semester`.
- **`subjects`**: Subjects linked to a specific preset.
    - *Columns*: `id`, `preset_id` (FK), `name`, `code`, `credits`.
- **`components`**: Assessment parts for a subject (e.g., IAT1, End Sem).
    - *Columns*: `id`, `subject_id` (FK), `name`, `max_marks`.

### Data Tables
- **`student_marks`**: Raw marks entered by students.
    - *Columns*: `user_id` (FK), `component_id` (FK), `marks_obtained`.
- **`subject_results`**: Calculated subject grades.
    - *Columns*: `user_id` (FK), `subject_id` (FK), `total_obtained`, `percentage`, `grade`, `grade_point`.
- **`cgpa`**: Final aggregated score.
    - *Columns*: `user_id` (FK), `cgpa`.

---

## 2. Page-by-Page Database Interaction

### A. Login & Authentication (`/` and `/authorize`)
1.  **User Login**: App receives Google Email.
2.  **Check User**: `SELECT * FROM users WHERE email = ?`
    -   *If found*: Checks if profile fields (`enrollment_number`, `department`, etc.) are filled.
    -   *If missing fields*: Redirects to `/additional_info`.
    -   *If Admin*: Redirects to `/admin`.
    -   *If Student*: Redirects to `/student`.
3.  **New User**: If email not found, `INSERT INTO users (email, name, ...)`.

### B. Admin Dashboard (`/admin`)
1.  **View Presets**: `SELECT * FROM presets`
    -   Displays list of all class presets.
2.  **Add Preset**: `INSERT INTO presets (academic_year, course, department, year, division, semester) ...`
3.  **Delete Preset**:
    -   `DELETE FROM subjects WHERE preset_id = ?` (and cascade components)
    -   `DELETE FROM presets WHERE id = ?`

### C. Student Dashboard (`/student`)
1.  **Identify Student**: `SELECT department, current_year FROM users WHERE email = ?`
2.  **Filter Presets**:
    -   Query: `SELECT * FROM presets WHERE year = ? AND department = ?`
    -   *Result*: Dropdown only shows relevant classes (e.g., "SE Computer Engineering").
3.  **Load Subjects**:
    -   User selects `preset_id`.
    -   `SELECT * FROM subjects WHERE preset_id = ?`
    -   `SELECT * FROM components WHERE subject_id = ?`
    -   *Result*: Generates the dynamic marks entry form.
4.  **Calculate CGPA (POST)**:
    -   **Save Marks**: `INSERT OR REPLACE INTO student_marks ...`
    -   **Calculate Grade**: Compare percentage with `grading_rules` table.
    -   **Save Result**: `INSERT OR REPLACE INTO subject_results ...`
    -   **Save CGPA**: `INSERT OR REPLACE INTO cgpa ...`

### D. View Results (`/result`)
1.  **Fetch Data**:
    -   Complex JOIN Query:
        ```sql
        SELECT p.year, p.semester, s.name, sr.grade, sr.grade_point
        FROM subject_results sr
        JOIN subjects s ON sr.subject_id = s.id
        JOIN presets p ON s.preset_id = p.id
        WHERE sr.user_id = ?
        ORDER BY p.year, p.semester
        ```
2.  **Display**: Groups results by Semester (Preset) and shows SGPA/CGPA.

---

## 3. Error Analysis: `sqlite3.OperationalError: no such column: department`
**The Issue**: The `presets` table in your `database.db` was created *before* we added the `department` feature. The web app is now trying to `INSERT` or `UPDATE` a `department` column that doesn't exist in your file.

**The Fix**: The database schema must be synchronized with the code.
1.  **Manual Fix**: Alter the table to add the column.
    ```sql
    ALTER TABLE presets ADD COLUMN department TEXT;
    ```
2.  **Automated Fix**: Run the updated `migration_tools/migrate_database.py`.
