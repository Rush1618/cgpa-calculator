import sqlite3
import os
import sys

def full_reset_import(old_db_path, new_db_path):
    print(f"Starting Full Reset & Import from '{old_db_path}' to '{new_db_path}'...")
    
    if not os.path.exists(old_db_path):
        print(f"Error: Old database '{old_db_path}' not found.")
        return False

    try:
        # 1. Connect to both databases
        old_conn = sqlite3.connect(old_db_path)
        new_conn = sqlite3.connect(new_db_path)
        
        old_cursor = old_conn.cursor()
        new_cursor = new_conn.cursor()

        # 2. Clear current data in NEW DB
        print("Clearing current data from new database...")
        # Clear student profiles (keeping admins)
        new_cursor.execute("DELETE FROM users WHERE is_admin = 0")
        
        tables_to_clear = ['cgpa', 'subject_results', 'student_marks', 'components', 'subjects', 'presets']
        for table in tables_to_clear:
            new_cursor.execute(f"DELETE FROM {table}")
        print("   Success: Current data cleared (except admins).")

        # 3. Read data from OLD DB
        print("Reading data from old database...")
        def get_all(table):
            try:
                old_cursor.execute(f"SELECT * FROM {table}")
                return old_cursor.fetchall()
            except sqlite3.OperationalError as e:
                print(f"   Warning: Table {table} not found in old DB: {e}")
                return []

        old_users = get_all('users')
        old_presets = get_all('presets')
        old_subjects = get_all('subjects')
        old_components = get_all('components')
        old_student_marks = get_all('student_marks')
        
        print(f"   Read {len(old_users)} users, {len(old_presets)} presets, {len(old_subjects)} subjects, {len(old_student_marks)} marks.")

        # 4. Import Users (Handle New Schema)
        print("Importing Users...")
        # Old: id, email, name, roll_number, is_admin
        # New: id, email, name, picture, is_admin, enrollment_number, department, academic_year, current_year
        for u in old_users:
            if u[4] == 1: # is_admin
                continue # Skip admin, we already have one
            
            new_cursor.execute(
                "INSERT INTO users (id, email, name, is_admin, roll_number, department, current_year) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (u[0], u[1], u[2], 0, u[3], 'Computer Engineering', 'SE')
            )

        # 5. Import Presets & Normalize
        print("Importing & Normalizing Presets...")
        for p in old_presets:
            # p: id, ac_year, course, year, div, sem
            # Normalize course to 'BE'
            new_cursor.execute(
                "INSERT INTO presets (id, academic_year, course, department, year, division, semester) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (p[0], p[1], 'BE', 'Computer Engineering', p[3], p[4], p[5])
            )
        
        # 6. Import Subjects
        print("Importing Subjects...")
        for s in old_subjects:
            new_cursor.execute("INSERT INTO subjects VALUES (?, ?, ?, ?, ?)", s)

        # 7. Import Components
        print("Importing Components...")
        for c in old_components:
            new_cursor.execute("INSERT INTO components VALUES (?, ?, ?, ?)", c)

        # 8. Import Marks (Convert to REAL)
        print("Importing Marks...")
        for m in old_student_marks:
            new_cursor.execute(
                "INSERT OR IGNORE INTO student_marks (id, user_id, component_id, marks_obtained) VALUES (?, ?, ?, ?)",
                (m[0], m[1], m[2], float(m[3]))
            )

        # 9. Re-calculate Results
        print("Re-calculating Subject Results...")
        
        def get_grade(percentage):
            new_cursor.execute("SELECT grade, grade_point FROM grading_rules WHERE ? >= min_percentage AND ? < max_percentage", (percentage, percentage))
            res = new_cursor.fetchone()
            if res: return res
            return ('F', 0.0)

        new_cursor.execute("SELECT DISTINCT user_id FROM student_marks")
        user_ids = [row[0] for row in new_cursor.fetchall()]
        
        for user_id in user_ids:
            new_cursor.execute("""
                SELECT DISTINCT s.id, s.credits 
                FROM subjects s 
                JOIN components c ON c.subject_id = s.id 
                JOIN student_marks sm ON sm.component_id = c.id 
                WHERE sm.user_id = ?
            """, (user_id,))
            subjects = new_cursor.fetchall()
            
            user_total_weighted_points = 0
            user_total_credits = 0
            
            for subj_id, credits in subjects:
                new_cursor.execute("""
                    SELECT SUM(sm.marks_obtained), SUM(c.max_marks) 
                    FROM student_marks sm 
                    JOIN components c ON sm.component_id = c.id 
                    WHERE sm.user_id = ? AND c.subject_id = ?
                """, (user_id, subj_id))
                tot_obtained, tot_max = new_cursor.fetchone()
                
                if tot_max and tot_max > 0:
                    percentage = (tot_obtained / tot_max) * 100
                    grade, grade_point = get_grade(percentage)
                    
                    new_cursor.execute(
                        "INSERT OR IGNORE INTO subject_results (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (user_id, subj_id, tot_obtained, tot_max, percentage, grade, grade_point)
                    )
                    
                    user_total_weighted_points += (grade_point * credits)
                    user_total_credits += credits
            
            if user_total_credits > 0:
                final_cgpa = user_total_weighted_points / user_total_credits
                new_cursor.execute(
                    "INSERT OR IGNORE INTO cgpa (user_id, cgpa) VALUES (?, ?)",
                    (user_id, final_cgpa)
                )

        new_conn.commit()
        old_conn.close()
        new_conn.close()
        
        print("\nFull Reset & Import completed successfully!")
        return True

    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    old_db = "migration_tools/database (10).db"
    new_db = "database.db"
    success = full_reset_import(old_db, new_db)
    sys.exit(0 if success else 1)
