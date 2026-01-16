import sqlite3

def migrate_marks():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Detect Source: ID 1 ("BE Computer Engineering")
    print("Searching for Source Preset (Legacy)...")
    # Looking for the specific 'bad' course name we saw in the dump
    cursor.execute("SELECT id FROM presets WHERE course='BE Computer Engineering'")
    source_match = cursor.fetchone()
    
    if not source_match:
        print("❌ Source preset (Course='BE Computer Engineering') not found. Maybe already migrated?")
        # Fallback: Check strictly by ID 1 if it has the wrong course name
        cursor.execute("SELECT id FROM presets WHERE id=1 AND course!='BE'")
        source_match = cursor.fetchone()
        
    if not source_match:
        print("❌ Could not identify the legacy source preset (ID 1 with bad course name). Aborting.")
        # Debug: list all
        cursor.execute("SELECT id, course FROM presets")
        print("Current Presets:", cursor.fetchall())
        return

    source_id = source_match[0]
    print(f"✅ Found Source Preset ID: {source_id}")

    # Check/Create Target: "BE" + "Computer Engineering"
    print("Searching/Creating Target Preset...")
    cursor.execute("""
        SELECT id FROM presets 
        WHERE course='BE' AND department='Computer Engineering' AND year='SE' AND division='A' AND semester='3'
    """)
    target_match = cursor.fetchone()
    
    if target_match:
        target_id = target_match[0]
        print(f"✅ Found Existing Target Preset ID: {target_id}")
    else:
        print("ℹ️  Creating New Target Preset...")
        cursor.execute("""
            INSERT INTO presets (academic_year, course, department, year, division, semester)
            VALUES ('2025-2026', 'BE', 'Computer Engineering', 'SE', 'A', '3')
        """)
        target_id = cursor.lastrowid
        print(f"✅ Created New Target Preset ID: {target_id}")
        
    if source_id == target_id:
        print("⚠️ Source and Target are the same. Nothing to do.")
        return

    # Copy Subjects and Components to Target (if not exist)
    print("Syncing Subjects/Components...")
    cursor.execute("SELECT * FROM subjects WHERE preset_id=?", (source_id,))
    source_subjects = cursor.fetchall()
    
    # Map: (SubjectName) -> TargetSubjectID
    subj_map = {}
    
    for s in source_subjects:
        # s: id, preset_id, name, code, credits
        s_name = s[2]
        s_code = s[3]
        s_credits = s[4]
        
        # Check if subject exists in target
        cursor.execute("SELECT id FROM subjects WHERE preset_id=? AND name=?", (target_id, s_name))
        existing_subj = cursor.fetchone()
        
        if existing_subj:
            t_subj_id = existing_subj[0]
        else:
            cursor.execute("INSERT INTO subjects (preset_id, name, code, credits) VALUES (?, ?, ?, ?)", 
                           (target_id, s_name, s_code, s_credits))
            t_subj_id = cursor.lastrowid
            
        subj_map[s[0]] = t_subj_id # SourceSubjID -> TargetSubjID

        # Sync Components
        cursor.execute("SELECT * FROM components WHERE subject_id=?", (s[0],))
        source_comps = cursor.fetchall()
        
        for c in source_comps:
            # c: id, subject_id, name, max_marks
            c_name = c[2]
            c_max = c[3]
            
            # Check exist in target subject
            cursor.execute("SELECT id FROM components WHERE subject_id=? AND name=?", (t_subj_id, c_name))
            existing_comp = cursor.fetchone()
            
            if not existing_comp:
                cursor.execute("INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)",
                               (t_subj_id, c_name, c_max))

    # Re-build Maps for Migration
    # Target Map: (SubjectName, ComponentName) -> TargetComponentID
    cursor.execute("SELECT s.name, c.name, c.id FROM subjects s JOIN components c ON c.subject_id = s.id WHERE s.preset_id=?", (target_id,))
    target_structure = cursor.fetchall()
    target_map = { (row[0], row[1]): row[2] for row in target_structure } # Case sensitive?

    # Source Map: SourceComponentID -> (SubjectName, ComponentName)
    cursor.execute("SELECT s.name, c.name, c.id FROM subjects s JOIN components c ON c.subject_id = s.id WHERE s.preset_id=?", (source_id,))
    source_structure = cursor.fetchall()
    source_map = { row[2]: (row[0], row[1]) for row in source_structure }

    # Migrate Marks
    print("Migrating Marks...")
    cursor.execute("""
        SELECT sm.id, sm.user_id, sm.component_id, sm.marks_obtained 
        FROM student_marks sm
        JOIN components c ON sm.component_id = c.id
        JOIN subjects s ON c.subject_id = s.id
        WHERE s.preset_id = ?
    """, (source_id,))
    
    marks_to_migrate = cursor.fetchall()
    print(f"Found {len(marks_to_migrate)} marks to migrate.")
    
    migrated_count = 0
    deleted_count = 0
    
    for mark in marks_to_migrate:
        mark_id, user_id, source_comp_id, obtained = mark
        
        if source_comp_id in source_map:
            key = source_map[source_comp_id]
            if key in target_map:
                target_comp_id = target_map[key]
                try:
                    cursor.execute(
                        "INSERT OR REPLACE INTO student_marks (user_id, component_id, marks_obtained) VALUES (?, ?, ?)",
                        (user_id, target_comp_id, obtained)
                    )
                    migrated_count += 1
                except Exception as e:
                    print(f"Error migrating mark {mark_id}: {e}")
            else:
                print(f"Skipping mark {mark_id}: No matching component {key} in target")
        
        # Delete old mark
        cursor.execute("DELETE FROM student_marks WHERE id=?", (mark_id,))
        deleted_count += 1

    # Delete Old Preset and its Contents (Components, Subjects, Preset)
    # Using delete_preset logic roughly
    print(f"Deleting Legacy Preset ID {source_id}...")
    cursor.execute("DELETE FROM subject_results WHERE subject_id IN (SELECT id FROM subjects WHERE preset_id=?)", (source_id,))
    cursor.execute("DELETE FROM components WHERE subject_id IN (SELECT id FROM subjects WHERE preset_id=?)", (source_id,))
    cursor.execute("DELETE FROM subjects WHERE preset_id=?", (source_id,))
    cursor.execute("DELETE FROM presets WHERE id=?", (source_id,))

    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"Migration Complete.")
    print(f"✅ Migrated {migrated_count} marks to New Preset ID {target_id}.")
    print(f"🗑️  Deleted Legacy Preset ID {source_id}.")

if __name__ == "__main__":
    migrate_marks()
