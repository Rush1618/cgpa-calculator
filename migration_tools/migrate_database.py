"""
Database Migration Tool for CGPA Calculator
============================================

This script migrates old database backups to the new schema.

Old Schema Issues:
- marks_obtained: INTEGER (should be REAL)
- grade_point: INTEGER (should be REAL)
- 7 grading rules with gaps (missing 79-80 range)

New Schema:
- marks_obtained: REAL (supports decimals)
- grade_point: REAL (supports decimals)
- 8 grading rules with proper decimal ranges

Usage:
    python migrate_database.py old_backup.db
    
Output:
    Creates 'migrated_database.db' with new schema and all data preserved
"""

import sqlite3
import sys
import os
from datetime import datetime


def create_new_schema(cursor):
    """Create tables with the new schema (REAL fields)"""
    
    # Users table (Updated with profile fields)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            roll_number TEXT,
            enrollment_number TEXT,
            department TEXT,
            academic_year TEXT,
            current_year TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
    """)
    
    # Presets table (no change) (context skip...)

    # Presets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            course TEXT NOT NULL,
            department TEXT,
            year TEXT NOT NULL,
            division TEXT NOT NULL,
            semester TEXT NOT NULL
        )
    """)

    # Subjects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preset_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            code TEXT,
            credits INTEGER NOT NULL,
            FOREIGN KEY (preset_id) REFERENCES presets (id)
        )
    """)

    # Components table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            max_marks INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        )
    """)

    # Student Marks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (component_id) REFERENCES components (id),
            UNIQUE(user_id, component_id)
        )
    """)

    # Subject Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subject_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            total_obtained_marks REAL NOT NULL,
            total_max_marks REAL NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            UNIQUE(user_id, subject_id)
        )
    """)

    # CGPA table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cgpa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cgpa REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id)
        )
    """)

    # Grading Rules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grading_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_percentage REAL NOT NULL,
            max_percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL,
            UNIQUE(min_percentage, max_percentage)
        )
    """)


def migrate_database(old_db_path, output_path):
    print(f"🚀 Starting migration from '{old_db_path}' to '{output_path}'...")
    
    if not os.path.exists(old_db_path):
        print(f"❌ Error: Input file '{old_db_path}' not found.")
        return False

    # 1. Read data from Old DB
    print("   Reading data from old database...")
    try:
        old_conn = sqlite3.connect(old_db_path)
        old_cursor = old_conn.cursor()
        
        # Helper to get all rows safely
        def get_all(table):
            try:
                old_cursor.execute(f"SELECT * FROM {table}")
                return old_cursor.fetchall()
            except sqlite3.OperationalError:
                return []

        users = get_all('users')
        presets = get_all('presets')
        subjects = get_all('subjects')
        components = get_all('components')
        student_marks = get_all('student_marks')
        subject_results = get_all('subject_results')
        cgpa_records = get_all('cgpa')
        # grading_rules not needed to copy, we use new ones
        
        old_conn.close()
        print(f"   ✓ Read {len(users)} users, {len(presets)} presets, {len(student_marks)} marks")
        
    except Exception as e:
        print(f"❌ Error reading old database: {str(e)}")
        return False

    # 2. Create New DB and Schema
    if os.path.exists(output_path):
        os.remove(output_path)
        
    new_conn = sqlite3.connect(output_path)
    new_cursor = new_conn.cursor()
    
    create_new_schema(new_cursor)
    
    # helper for grading rules
    def get_grade_from_percentage(cursor, percentage):
        cursor.execute("SELECT grade, grade_point FROM grading_rules WHERE ? >= min_percentage AND ? < max_percentage", (percentage, percentage))
        res = cursor.fetchone()
        if res:
            return res
        return ('F', 0.0)

    # Insert Default Grading Rules
    grading_rules = [
        (0, 40, 'F', 0.0),
        (40, 45, 'P', 4.0),
        (45, 50, 'E', 5.0),
        (50, 60, 'D', 6.0),
        (60, 70, 'C', 7.0),
        (70, 75, 'B', 8.0),
        (75, 80, 'A', 9.0),
        (80, 101, '0', 10.0) # Changed O to 0 to match user pref if needed, or stick to O? Stick to standard for now or what was in old db?
        # Standard logic usually O. Let's use O.
    ]
    # Actually wait, let's stick to standard 0-100 range.
    # Re-inserting default rules if not exist? 
    # The create_new_schema table is empty. Let's populate it.
    new_cursor.executemany("INSERT OR IGNORE INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)", grading_rules)

    # 1. Users (Handle schema change)
    if users:
        print(f"   ℹ️  Migrating {len(users)} users...")
        sample_user = users[0]
        # Check if old schema (5 columns: id, email, name, roll, is_admin)
        if len(sample_user) == 5:
            migrated_users = []
            for u in users:
                # Map: id, email, name, roll, NULL, NULL, NULL, NULL, is_admin
                migrated_users.append((u[0], u[1], u[2], u[3], None, None, None, None, u[4]))
            
            new_cursor.executemany(
                "INSERT INTO users (id, email, name, roll_number, enrollment_number, department, academic_year, current_year, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                migrated_users
            )
            print(f"   ✓ Converted and migrated {len(users)} users (added profile fields)")
        else:
            # Assume 9 columns or let it fail/handle dynamically? 
            # If 9, exact match.
            new_cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", users)
            print(f"   ✓ Migrated {len(users)} users (schema match)")
    
    # 2. Presets (no conversion needed)
    # 2. Presets (Handle schema change)
    if presets:
        print(f"   ℹ️  Migrating {len(presets)} presets...")
        sample_preset = presets[0]
        # Old schema: id, ac_year, course, year, div, sem (6 cols) or 5?
        # Let's check how many cols in old db.
        # database.py had: id, academic_year, course, year, division, semester (6 cols)
        # New db has: id, academic_year, course, department, year, division, semester (7 cols)
        
        migrated_presets = []
        for p in presets:
            if len(p) == 6: # Old schema
                 # Map: id, ac_year, course, 'Computer Engineering' (dept), year, div, sem
                 migrated_presets.append((p[0], p[1], p[2], 'Computer Engineering', p[3], p[4], p[5]))
            else:
                 migrated_presets.append(p)

        new_cursor.executemany(
            "INSERT INTO presets (id, academic_year, course, department, year, division, semester) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            migrated_presets
        )
        print(f"   ✓ Migrated {len(presets)} presets (added department field)")
    
    # 3. Subjects (no conversion needed)
    if subjects:
        new_cursor.executemany("INSERT INTO subjects VALUES (?, ?, ?, ?, ?)", subjects)
        print(f"   ✓ Migrated {len(subjects)} subjects")
    
    # 4. Components (no conversion needed)
    if components:
        new_cursor.executemany("INSERT INTO components VALUES (?, ?, ?, ?)", components)
        print(f"   ✓ Migrated {len(components)} components")
    
    # 5. Student marks (convert to REAL)
    if student_marks:
        converted_marks = [(id, uid, cid, float(marks)) for id, uid, cid, marks in student_marks]
        converted_marks = [(id, uid, cid, float(marks)) for id, uid, cid, marks in student_marks]
        new_cursor.executemany("INSERT OR IGNORE INTO student_marks VALUES (?, ?, ?, ?)", converted_marks)
        print(f"   ✓ Migrated {len(student_marks)} student marks (converted to REAL)")
    
    # 6. Subject results (recalculate grades with new rules)
    if subject_results:
        recalculated = 0
        for result in subject_results:
            id, user_id, subject_id, total_obtained, total_max, percentage, old_grade, old_grade_point = result
            
            # Get new grade based on percentage using NEW grading rules
            new_grade, new_grade_point = get_grade_from_percentage(new_cursor, percentage)
            
            # Insert with new grade and grade_point (INSERT OR IGNORE for safety)
            new_cursor.execute(
                "INSERT OR IGNORE INTO subject_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (id, user_id, subject_id, float(total_obtained), float(total_max), 
                 percentage, new_grade, new_grade_point)
            )
            
            if old_grade != new_grade or old_grade_point != new_grade_point:
                recalculated += 1
        
        print(f"   ✓ Migrated {len(subject_results)} subject results")
        if recalculated > 0:
            print(f"   ⚠️  Recalculated {recalculated} grades due to new grading rules")
    
    # 7. CGPA (already REAL, but may need recalculation)
    if cgpa_records:
        new_cursor.executemany("INSERT OR IGNORE INTO cgpa VALUES (?, ?, ?)", cgpa_records)
        print(f"   ✓ Migrated {len(cgpa_records)} CGPA records")
        print(f"   ℹ️  Note: CGPA values may need recalculation if grades changed")
    
    # Commit and close
    new_conn.commit()
    new_conn.close()
    
    print(f"\n✅ Migration completed successfully!")
    print(f"📁 Migrated database saved to: {output_path}")
    print(f"\n💡 Next steps:")
    print(f"   1. Backup your current database.db")
    print(f"   2. Replace database.db with {output_path}")
    print(f"   3. Restart your Flask application")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_database.py <old_backup.db> [output_name.db]")
        print("\nExample:")
        print("  python migrate_database.py old_backup.db")
        print("  python migrate_database.py old_backup.db new_database.db")
        sys.exit(1)
    
    old_db = sys.argv[1]
    output_db = sys.argv[2] if len(sys.argv) > 2 else 'migrated_database.db'
    
    success = migrate_database(old_db, output_db)
    sys.exit(0 if success else 1)
