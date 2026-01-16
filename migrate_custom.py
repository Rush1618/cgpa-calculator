import sqlite3
import os

OLD_DB = "database_backup.db"
NEW_DB = "database.db"

def migrate():
    print("Starting custom migration...")
    if not os.path.exists(OLD_DB):
        print(f"Error: {OLD_DB} not found!")
        return

    old = sqlite3.connect(OLD_DB)
    new = sqlite3.connect(NEW_DB)

    old_cur = old.cursor()
    new_cur = new.cursor()

    # 0 CLEAR NEW DB TABLES FOR FRESH IMPORT
    print("Clearing new database...")
    tables = ['cgpa', 'subject_results', 'student_marks', 'components', 'subjects', 'presets', 'users']
    for table in tables:
        try:
            new_cur.execute(f"DELETE FROM {table}")
        except:
            pass
    new.commit()

    # 1 MIGRATE USERS
    print("Migrating users...")
    old_cur.execute("SELECT id, email, name, roll_number, is_admin FROM users")
    users = old_cur.fetchall()

    for u in users:
        new_cur.execute("""
            INSERT INTO users
            (id, email, name, roll_number, enrollment_number, department, academic_year, current_year, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            u[0],                     # id
            u[1],                     # email
            u[2],                     # name
            u[3],                     # roll
            None,                     # enrollment_number
            "Computer Engineering",   # department
            "2025-2026",              # academic year
            "SE",                     # current year
            u[4]                      # is_admin
        ))

    # 2 CREATE SINGLE NEW PRESET (PRESET-1)
    print("Creating new preset...")
    new_cur.execute("""
        INSERT INTO presets
        (academic_year, course, department, year, division, semester)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "2025-2026",
        "B.E",
        "Computer Engineering",
        "SE",
        "A",
        "3"
    ))

    new_preset_id = new_cur.lastrowid

    # 3 MIGRATE SUBJECTS
    print("Migrating subjects...")
    old_cur.execute("SELECT id, name, code, credits FROM subjects")
    subjects = old_cur.fetchall()

    subject_map = {}  # old_id -> new_id

    for s in subjects:
        new_cur.execute("""
            INSERT INTO subjects (preset_id, name, code, credits)
            VALUES (?, ?, ?, ?)
        """, (
            new_preset_id,
            s[1],
            s[2],
            s[3]
        ))
        subject_map[s[0]] = new_cur.lastrowid

    # 4 MIGRATE COMPONENTS
    print("Migrating components...")
    old_cur.execute("SELECT id, subject_id, name, max_marks FROM components")
    components = old_cur.fetchall()

    component_map = {}

    for c in components:
        if c[1] not in subject_map:
            continue
        new_subject_id = subject_map[c[1]]
        new_cur.execute("""
            INSERT INTO components (subject_id, name, max_marks)
            VALUES (?, ?, ?)
        """, (
            new_subject_id,
            c[2],
            c[3]
        ))
        component_map[c[0]] = new_cur.lastrowid

    # 5 MIGRATE STUDENT MARKS
    print("Migrating marks...")
    old_cur.execute("SELECT user_id, component_id, marks_obtained FROM student_marks")
    marks = old_cur.fetchall()

    for m in marks:
        if m[1] not in component_map:
            continue
        new_cur.execute("""
            INSERT OR IGNORE INTO student_marks (user_id, component_id, marks_obtained)
            VALUES (?, ?, ?)
        """, (
            m[0],
            component_map[m[1]],
            m[2]
        ))

    # 6 MIGRATE SUBJECT RESULTS
    print("Migrating subject results...")
    old_cur.execute("""
        SELECT user_id, subject_id, total_obtained, total_max, percentage, grade, grade_point
        FROM subject_results
    """)
    results = old_cur.fetchall()

    for r in results:
        if r[1] not in subject_map:
            continue
        new_cur.execute("""
            INSERT OR IGNORE INTO subject_results
            (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            r[0],
            subject_map[r[1]],
            r[2],
            r[3],
            r[4],
            r[5],
            r[6]
        ))

    # 7 MIGRATE CGPA
    print("Migrating CGPA...")
    old_cur.execute("SELECT user_id, cgpa FROM cgpa")
    cgpas = old_cur.fetchall()

    for c in cgpas:
        new_cur.execute("""
            INSERT OR IGNORE INTO cgpa (user_id, cgpa)
            VALUES (?, ?)
        """, (c[0], c[1]))

    new.commit()
    old.close()
    new.close()

    print("Success: Migration completed successfully")

if __name__ == "__main__":
    migrate()
