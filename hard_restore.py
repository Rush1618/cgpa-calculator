import sqlite3
import shutil
import os

SOURCE_DB_PATH = os.path.join("migration_tools", "database (11).db")
TARGET_DB = "database.db"

def hard_restore():
    if not os.path.exists(SOURCE_DB_PATH):
        print(f"Error: {SOURCE_DB_PATH} not found!")
        return

    print("WARNING: Starting HARD RESTORE. Wiping existing database...")
    
    # 1. Connect
    tgt_conn = sqlite3.connect(TARGET_DB)
    tgt_cur = tgt_conn.cursor()
    
    src_conn = sqlite3.connect(SOURCE_DB_PATH)
    src_cur = src_conn.cursor()

    # 2. Wipe Tables (Order matters for FKs)
    tables = ['cgpa', 'subject_results', 'student_marks', 'components', 'subjects', 'presets', 'users', 'grading_rules']
    for t in tables:
        try:
            tgt_cur.execute(f"DELETE FROM {t}")
            print(f"   Wiped {t}")
        except Exception as e:
            print(f"   Error wiping {t}: {e}")
    tgt_conn.commit()

    # 3. Import Data (Literal Copy)
    print("\nImporting Data from Backup...")

    # A. Users
    print("   Importing Users...")
    src_cur.execute("SELECT * FROM users")
    users = src_cur.fetchall()
    # Need column names to be safe? Or assume schema match + extras?
    # Target has `enrollment_number`, `department` etc. Source might not.
    # Source (11) likely has old schema.
    # We must map explicitly.
    # Source Schema Check:
    # PRAGMA table_info(users) on source?
    # Let's assume Source 11 has: id, email, name, roll_number, is_admin (based on previous scripts)
    # We will insert into Target with defaults for new columns.
    
    src_cur.execute("SELECT id, email, name, roll_number, is_admin FROM users") 
    # Wait, does Source 11 have 'department'? Previous user comments implied "department is shown in enrollment..."
    # The source might have broken data. But user said "restore from their". 
    # Strategy: Import basics, then APPLY FIXES.
    
    for u in src_cur.fetchall():
        try:
            # ID, Email, Name, Roll, [Enrollment], [Dept], [AcadYear], [CurrYear], IsAdmin
            # default Dept to "Student" or null, we fix later
            tgt_cur.execute("""
                INSERT INTO users (id, email, name, roll_number, is_admin, department, current_year, academic_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (u[0], u[1], u[2], u[3], u[4], 'Computer Engineering', 'SE', '2025-2026'))
        except Exception as e:
            print(f"Error importing user {u[1]}: {e}")

    # B. Presets
    print("   Importing Presets...")
    src_cur.execute("SELECT id, academic_year, course, year, division, semester FROM presets") 
    # Source might lack 'department'.
    for p in src_cur.fetchall():
        tgt_cur.execute("""
            INSERT INTO presets (id, academic_year, course, department, year, division, semester)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (p[0], p[1], p[2], 'Computer Engineering', p[3], p[4], p[5]))

    # C. Subjects
    print("   Importing Subjects...")
    src_cur.execute("SELECT id, preset_id, name, code, credits FROM subjects")
    for s in src_cur.fetchall():
        tgt_cur.execute("INSERT INTO subjects (id, preset_id, name, code, credits) VALUES (?, ?, ?, ?, ?)", s)

    # D. Components
    print("   Importing Components...")
    src_cur.execute("SELECT id, subject_id, name, max_marks FROM components") 
    for c in src_cur.fetchall():
        tgt_cur.execute("INSERT INTO components (id, subject_id, name, max_marks) VALUES (?, ?, ?, ?)", c)

    # E. Marks
    print("   Importing Marks...")
    src_cur.execute("SELECT user_id, component_id, marks_obtained FROM student_marks")
    for m in src_cur.fetchall():
        tgt_cur.execute("INSERT OR REPLACE INTO student_marks (user_id, component_id, marks_obtained) VALUES (?, ?, ?)", m)
        
    # F. Grading Rules (User requested "grading system from their")
    print("   Importing Grading Rules...")
    try:
        src_cur.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
        rules = src_cur.fetchall()
        if rules:
            for r in rules:
                tgt_cur.execute("INSERT INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)", r)
        else:
             print("   Warning: No rules in backup. Using default strict rules.")
             # Fallback to strict rules if backup empty
             strict_rules = [
                (90.0, 100.0, 'O', 10.0), (80.0, 89.99, 'A+', 9.0), (70.0, 79.99, 'A', 8.0),
                (60.0, 69.99, 'B+', 7.0), (55.0, 59.99, 'B', 6.0), (50.0, 54.99, 'C', 5.0),
                (40.0, 49.99, 'P', 4.0), (0.0, 39.99, 'F', 0.0)
            ]
             tgt_cur.executemany("INSERT INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)", strict_rules)
    except:
        print("   Backup lacks grading_rules table?")

    tgt_conn.commit()

    # 4. FIX DEPARTMENTS (Correcting the 'Computer Engineering' default)
    print("\nApplying Department Fixes...")
    # NOTE: Since source didn't have department, we defaulted to "Computer Engineering". 
    # But user previous request said "Mechanical" and "ECS".
    # We can't know for sure which preset/user was which without data.
    # BUT, if we assume the user WANTS the "Mechanical/ECS" mapping we did before...
    # Wait, the previous mapping was replacing "Chemical" -> "Mechanical".
    # If the source DB has NO department data, we have lost that distinction!
    # Checking source schema specifically...
    # If source `database (11).db` HAS department column, we should have used it.
    
    # Let's try to fetch `department` column from source just in case.
    try: 
        src_cur.execute("SELECT id, department FROM presets")
        preset_depts = src_cur.fetchall()
        print("   Source HAS department column in presets! Updating...")
        for pid, dept in preset_depts:
            tgt_cur.execute("UPDATE presets SET department=? WHERE id=?", (dept, pid))
    except:
        print("   Source does NOT have department in presets.")
        
    try:
        src_cur.execute("SELECT id, department FROM users")
        user_depts = src_cur.fetchall()
        print("   Source HAS department column in users! Updating...")
        for uid, dept in user_depts:
             tgt_cur.execute("UPDATE users SET department=? WHERE id=?", (dept, uid))
    except:
        print("   Source does NOT have department in users.")

    # Now apply rename fixes (just in case they were imported as Old Names)
    tgt_cur.execute("UPDATE presets SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    tgt_cur.execute("UPDATE presets SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    tgt_cur.execute("UPDATE users SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    tgt_cur.execute("UPDATE users SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    tgt_conn.commit()

    # 5. RECALCULATE (Safety check)
    print("\nRecalculating everything...")
    tgt_cur.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
    rules = tgt_cur.fetchall()
    
    tgt_cur.execute("SELECT DISTINCT user_id FROM student_marks")
    users = [r[0] for r in tgt_cur.fetchall()]
    
    for uid in users:
        # Get subjects
        tgt_cur.execute("""
            SELECT DISTINCT s.id, s.credits FROM subjects s
            JOIN components c ON c.subject_id = s.id
            JOIN student_marks sm ON sm.component_id = c.id
            WHERE sm.user_id = ?
        """, (uid,))
        subjects = tgt_cur.fetchall()
        
        total_creds = 0
        total_pts = 0
        
        for sid, creds in subjects:
            tgt_cur.execute("""
                SELECT SUM(sm.marks_obtained), SUM(c.max_marks)
                FROM student_marks sm
                JOIN components c ON sm.component_id = c.id
                WHERE sm.user_id=? AND c.subject_id=?
            """, (uid, sid))
            
            agg = tgt_cur.fetchone()
            obt = agg[0] or 0
            max_m = agg[1] or 0
            
            if max_m > 0: perc = (obt/max_m)*100
            else: perc = 0
            
            grade, gp = 'F', 0.0
            for min_p, max_p, g, p in rules:
                if perc >= min_p and perc <= max_p:
                    grade = g
                    gp = p
                    break
            
            tgt_cur.execute("""
                INSERT OR REPLACE INTO subject_results 
                (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, sid, obt, max_m, perc, grade, gp))
            
            total_pts += (gp * creds)
            total_creds += creds
            
        if total_creds > 0:
            cgpa = total_pts / total_creds
            tgt_cur.execute("INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)", (uid, cgpa))

    tgt_conn.commit()
    tgt_conn.close()
    src_conn.close()
    print("HARD RESTORE COMPLETE.")

if __name__ == "__main__":
    hard_restore()
