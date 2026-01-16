import sqlite3
import os

SOURCE_DB = "database_import.db"
TARGET_DB = "database.db"
TARGET_PRESET_ID = 5 # As identified earlier for 'Computer Engineering | SE'

def append_migration():
    print(f"Starting APPEND migration from {SOURCE_DB} to {TARGET_DB}...")
    
    if not os.path.exists(SOURCE_DB):
        print(f"Error: {SOURCE_DB} not found!")
        return

    source = sqlite3.connect(SOURCE_DB)
    target = sqlite3.connect(TARGET_DB)

    src_cur = source.cursor()
    tgt_cur = target.cursor()

    # 1. MIGRATE USERS (APPEND ONLY)
    print("Migrating users...")
    src_cur.execute("SELECT id, email, name, roll_number, is_admin FROM users")
    users = src_cur.fetchall()
    
    count_users = 0
    for u in users:
        # Check if user email already exists to avoid unique constraint failure on email
        tgt_cur.execute("SELECT id FROM users WHERE email=?", (u[1],))
        existing = tgt_cur.fetchone()
        
        if existing:
            # print(f"Skipping existing user: {u[1]}")
            pass
        else:
            # Insert new user
            try:
                tgt_cur.execute("""
                    INSERT INTO users
                    (email, name, roll_number, department, academic_year, current_year, is_admin)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    u[1],                     # email
                    u[2],                     # name
                    u[3],                     # roll
                    "Computer Engineering",   # department
                    "2025-2026",              # academic year
                    "SE",                     # current year
                    u[4]                      # is_admin
                ))
                count_users += 1
            except sqlite3.IntegrityError:
                # Fallback if ID collision or other constraint
                pass
    
    print(f"   Success: Added {count_users} new users.")

    # 2. MAP SUBJECTS (Match by Name/Code)
    print("Mapping subjects...")
    # Get target subjects
    tgt_cur.execute("SELECT id, name, code FROM subjects WHERE preset_id=?", (TARGET_PRESET_ID,))
    target_subjects = tgt_cur.fetchall() # [(id, name, code), ...]
    
    # Map Code/Name -> Target ID
    tgt_subj_map = {} 
    for s in target_subjects:
        key = (s[2].strip().lower() if s[2] else "") # Use code as primary key if available
        tgt_subj_map[key] = s[0]
        # Also map by name just in case
        tgt_subj_map[s[1].strip().lower()] = s[0]

    # Get source subjects
    src_cur.execute("SELECT id, name, code FROM subjects")
    source_subjects = src_cur.fetchall()
    
    # Map Source ID -> Target ID
    src_to_tgt_subj = {}
    for s in source_subjects:
        code_key = (s[2].strip().lower() if s[2] else "")
        name_key = s[1].strip().lower()
        
        if code_key in tgt_subj_map:
            src_to_tgt_subj[s[0]] = tgt_subj_map[code_key]
        elif name_key in tgt_subj_map:
            src_to_tgt_subj[s[0]] = tgt_subj_map[name_key]
        else:
            print(f"   Warning: Could not map subject '{s[1]}' ({s[2]}). Skipping marks for this subject.")
            
    # 3. MAP COMPONENTS
    print("Mapping components...")
    # Get target components
    tgt_cur.execute("""
        SELECT c.id, c.name, c.subject_id 
        FROM components c 
        JOIN subjects s ON c.subject_id = s.id 
        WHERE s.preset_id = ?
    """, (TARGET_PRESET_ID,))
    target_components = tgt_cur.fetchall()
    
    # Map (SubjectID_Target, CompName) -> TargetCompID
    tgt_comp_map = {}
    for c in target_components:
        tgt_comp_map[(c[2], c[1].strip().lower())] = c[0]
        
    # Get source components
    src_cur.execute("SELECT id, subject_id, name FROM components")
    source_components = src_cur.fetchall()
    
    # Map Source ID -> Target ID
    src_to_tgt_comp = {}
    for c in source_components:
        src_subj_id = c[1]
        if src_subj_id not in src_to_tgt_subj:
            continue
            
        tgt_subj_id = src_to_tgt_subj[src_subj_id]
        comp_name_key = c[2].strip().lower()
        
        if (tgt_subj_id, comp_name_key) in tgt_comp_map:
            src_to_tgt_comp[c[0]] = tgt_comp_map[(tgt_subj_id, comp_name_key)]
    
    # 4. MIGRATE MARKS
    print("Migrating marks...")
    src_cur.execute("SELECT user_id, component_id, marks_obtained FROM student_marks")
    marks = src_cur.fetchall()
    
    count_marks = 0
    for m in marks:
        # Find Target User ID (Assume email match)
        src_cur.execute("SELECT email FROM users WHERE id=?", (m[0],))
        u_res = src_cur.fetchone()
        if not u_res: continue
        email = u_res[0]
        
        tgt_cur.execute("SELECT id FROM users WHERE email=?", (email,))
        t_u_res = tgt_cur.fetchone()
        if not t_u_res: continue
        target_user_id = t_u_res[0]
        
        # Find Target Component ID
        if m[1] not in src_to_tgt_comp:
            continue
        target_comp_id = src_to_tgt_comp[m[1]]
        
        # Insert
        try:
            tgt_cur.execute("""
                INSERT OR IGNORE INTO student_marks (user_id, component_id, marks_obtained)
                VALUES (?, ?, ?)
            """, (target_user_id, target_comp_id, m[2]))
            if tgt_cur.rowcount > 0:
                count_marks += 1
        except Exception as e:
            print(f"Error inserting mark: {e}")

    print(f"   Success: Migrated {count_marks} marks.")

    # 5. RECALCULATE RESULTS (Since we added new marks)
    print("Recalculating Subject Results for affected users...")
    # (Reuse logic from previous script, or just trust the app to recalc on view? 
    # Better to force a recalc for consistency)
    
    # Simple approach: Identify all users who got new marks
    # For now, let's just commit. The system might calculate on the fly or we can run a recalc script.
    # Given the previous script logic, let's do a quick recalc for ALL users to be safe.
    
    tgt_cur.execute("SELECT grade, grade_point, min_percentage, max_percentage FROM grading_rules")
    rules = tgt_cur.fetchall()

    def get_grade(percentage):
        for r in rules:
            if percentage >= r[2] and percentage < r[3]:
                return (r[0], r[1])
        return ('F', 0.0)

    # Get all users
    tgt_cur.execute("SELECT id FROM users WHERE is_admin=0")
    all_student_ids = [r[0] for r in tgt_cur.fetchall()]
    
    for uid in all_student_ids:
        # Get subjects for this user (where they have marks)
        tgt_cur.execute("""
            SELECT DISTINCT s.id, s.credits 
            FROM subjects s 
            JOIN components c ON c.subject_id = s.id 
            JOIN student_marks sm ON sm.component_id = c.id 
            WHERE sm.user_id = ?
        """, (uid,))
        subjects = tgt_cur.fetchall()
        
        total_credits = 0
        total_points = 0
        
        for sid, credits in subjects:
            tgt_cur.execute("""
                SELECT SUM(sm.marks_obtained), SUM(c.max_marks) 
                FROM student_marks sm 
                JOIN components c ON sm.component_id = c.id 
                WHERE sm.user_id = ? AND c.subject_id = ?
            """, (uid, sid))
            res = tgt_cur.fetchone()
            if not res or res[0] is None: continue
            
            obt, max_m = res
            if max_m > 0:
                perc = (obt / max_m) * 100
                grade, gp = get_grade(perc)
                
                # Update Subject Result
                tgt_cur.execute("""
                    INSERT OR REPLACE INTO subject_results 
                    (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (uid, sid, obt, max_m, perc, grade, gp))
                
                total_points += (gp * credits)
                total_credits += credits

        if total_credits > 0:
            cgpa = total_points / total_credits
            tgt_cur.execute("INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)", (uid, cgpa))

    target.commit()
    source.close()
    target.close()
    print("Success: Append migration completed.")

if __name__ == "__main__":
    append_migration()
