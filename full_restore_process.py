import sqlite3
import shutil
import os

SOURCE_DB_PATH = os.path.join("migration_tools", "database (11).db")
TARGET_DB = "database.db"
# Target Preset ID for "SE | Computer Engineering" (adjust if needed, usually 5 based on history)
TARGET_PRESET_ID = 5 

def full_restore_process():
    if not os.path.exists(SOURCE_DB_PATH):
        print(f"Error: {SOURCE_DB_PATH} not found!")
        return

    print(f"Starting FULL RESTORE from {SOURCE_DB_PATH}...")
    source = sqlite3.connect(SOURCE_DB_PATH)
    target = sqlite3.connect(TARGET_DB)
    src_cur = source.cursor()
    tgt_cur = target.cursor()

    # 1. MIGRATE USERS
    print("\n1. Migrating Users...")
    src_cur.execute("SELECT id, email, name, roll_number, is_admin FROM users")
    users = src_cur.fetchall()
    
    count_users = 0
    for u in users:
        # Check existence
        tgt_cur.execute("SELECT id FROM users WHERE email=?", (u[1],))
        if tgt_cur.fetchone():
            # Update existing user ensuring details are synced?
            # User might want old data back. Let's update basic info but keep admin flag if set locally?
            # Actually, user wants "import again". Let's update details.
            # But wait, department names in old DB are "Chemical" etc. we fix that later.
            pass
        else:
            try:
                tgt_cur.execute("""
                    INSERT INTO users (email, name, roll_number, department, academic_year, current_year, is_admin)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (u[1], u[2], u[3], "Computer Engineering", "2025-2026", "SE", u[4]))
                count_users += 1
            except Exception as e:
                print(f"   Error adding user {u[1]}: {e}")
    print(f"   Added {count_users} new users.")

    # 2. MAP SUBJECTS & COMPONENTS (Reusing proven logic)
    print("\n2. Mapping Subjects & Components...")
    
    # Target Maps
    tgt_cur.execute("SELECT id, name, code FROM subjects WHERE preset_id=?", (TARGET_PRESET_ID,))
    tgt_subjects = tgt_cur.fetchall()
    tgt_subj_map = {s[1].strip().lower(): s[0] for s in tgt_subjects}
    
    # Source Subjects
    src_cur.execute("SELECT id, name, code FROM subjects")
    src_subjects = src_cur.fetchall()
    src_to_tgt_subj = {}
    for s in src_subjects:
        if s[1].strip().lower() in tgt_subj_map:
            src_to_tgt_subj[s[0]] = tgt_subj_map[s[1].strip().lower()]

    # Components
    tgt_cur.execute("SELECT c.id, c.name, s.id FROM components c JOIN subjects s ON c.subject_id = s.id WHERE s.preset_id=?", (TARGET_PRESET_ID,))
    tgt_comps = tgt_cur.fetchall()
    tgt_comp_map = {(c[2], c[1].strip().lower()): c[0] for c in tgt_comps}

    src_cur.execute("SELECT id, subject_id, name FROM components")
    src_comps = src_cur.fetchall()
    src_to_tgt_comp = {}
    for c in src_comps:
        if c[1] in src_to_tgt_subj:
            key = (src_to_tgt_subj[c[1]], c[2].strip().lower())
            if key in tgt_comp_map:
                src_to_tgt_comp[c[0]] = tgt_comp_map[key]

    # 3. MIGRATE MARKS
    print("\n3. Migrating Marks...")
    src_cur.execute("SELECT user_id, component_id, marks_obtained FROM student_marks")
    marks = src_cur.fetchall()
    
    count_marks = 0
    for m in marks:
        # Get Email to find Target User ID
        src_cur.execute("SELECT email FROM users WHERE id=?", (m[0],))
        u_res = src_cur.fetchone()
        if not u_res: continue
        
        tgt_cur.execute("SELECT id FROM users WHERE email=?", (u_res[0],))
        t_u_res = tgt_cur.fetchone()
        if not t_u_res: continue
        
        target_uid = t_u_res[0]
        if m[1] in src_to_tgt_comp:
            target_comp = src_to_tgt_comp[m[1]]
            tgt_cur.execute("""
                INSERT OR REPLACE INTO student_marks (user_id, component_id, marks_obtained)
                VALUES (?, ?, ?)
            """, (target_uid, target_comp, m[2]))
            count_marks += 1
            
    print(f"   Imported {count_marks} marks.")
    target.commit()

    # 4. FIX DEPARTMENTS
    print("\n4. Fixing Department Names...")
    tgt_cur.execute("UPDATE presets SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    tgt_cur.execute("UPDATE presets SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    tgt_cur.execute("UPDATE users SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    tgt_cur.execute("UPDATE users SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    target.commit()

    # 5. RECALCULATE GRADES (Strict Schema)
    print("\n5. Recalculating Grading & CGPA...")
    
    # Clean invalid marks first
    tgt_cur.execute("UPDATE student_marks SET marks_obtained = 0 WHERE marks_obtained < 0")
    
    tgt_cur.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
    rules = tgt_cur.fetchall() # Using the currently configured strict rules

    # Get all results to recalc
    tgt_cur.execute("SELECT user_id, subject_id, total_obtained_marks, total_max_marks FROM subject_results")
    results = tgt_cur.fetchall()
    
    recalc_count = 0
    for user_id, subject_id, obt, total_max in results:
        # NOTE: Total Obtained/Max might be stale in subject_results if we just imported new marks into student_marks!
        # We MUST re-aggregate from student_marks to be sure.
        
        tgt_cur.execute("""
            SELECT SUM(sm.marks_obtained), SUM(c.max_marks)
            FROM student_marks sm
            JOIN components c ON sm.component_id = c.id
            WHERE sm.user_id=? AND c.subject_id=?
        """, (user_id, subject_id))
        agg = tgt_cur.fetchone()
        
        real_obt = agg[0] if agg and agg[0] is not None else 0
        real_max = agg[1] if agg and agg[1] is not None else 0
        
        if real_max > 0:
            perc = (real_obt / real_max) * 100
        else:
            perc = 0
            
        new_grade = 'F'
        new_point = 0.0
        for min_p, max_p, g, p in rules:
            if perc >= min_p and perc <= max_p:
                new_grade = g
                new_point = p
                break
                
        tgt_cur.execute("""
            UPDATE subject_results 
            SET total_obtained_marks=?, total_max_marks=?, percentage=?, grade=?, grade_point=?
            WHERE user_id=? AND subject_id=?
        """, (real_obt, real_max, perc, new_grade, new_point, user_id, subject_id))
        recalc_count += 1

    target.commit()
    print(f"   Recalculated {recalc_count} subject results.")

    # 6. Recalculate CGPA Table
    print("\n6. Updating Final CGPA...")
    # Get all users with results
    tgt_cur.execute("SELECT DISTINCT user_id FROM subject_results")
    users_with_results = tgt_cur.fetchall()
    
    for (stats_uid,) in users_with_results:
        tgt_cur.execute("""
            SELECT SUM(sr.grade_point * s.credits), SUM(s.credits)
            FROM subject_results sr
            JOIN subjects s ON sr.subject_id = s.id
            WHERE sr.user_id = ?
        """, (stats_uid,))
        cgpa_stats = tgt_cur.fetchone()
        
        if cgpa_stats and cgpa_stats[1] and cgpa_stats[1] > 0:
            final_cgpa = cgpa_stats[0] / cgpa_stats[1]
            tgt_cur.execute("INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)", (stats_uid, final_cgpa))

    target.commit()
    source.close()
    target.close()
    print("\nFULL RESTORE & UPDATE COMPLETE.")

if __name__ == "__main__":
    full_restore_process()
