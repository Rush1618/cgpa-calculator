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
    
    # Users table (no change)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            roll_number TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
    """)
    
    # Presets table (no change)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_year TEXT NOT NULL,
            course TEXT NOT NULL,
            year TEXT NOT NULL,
            division TEXT NOT NULL,
            semester TEXT NOT NULL
        )
    """)
    
    # Subjects table (no change)
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
    
    # Components table (no change)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            max_marks INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        )
    """)
    
    # Student marks - CHANGED: marks_obtained to REAL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            component_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (component_id) REFERENCES components (id)
        )
    """)
    
    # Subject results - CHANGED: total_obtained, total_max, grade_point to REAL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subject_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            total_obtained REAL NOT NULL,
            total_max REAL NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        )
    """)
    
    # CGPA table (already REAL)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cgpa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cgpa REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Grading rules - CHANGED: min/max percentage and grade_point to REAL
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grading_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_percentage REAL NOT NULL,
            max_percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL
        )
    """)
    
    # Insert NEW grading rules (8 rules with proper ranges)
    new_rules = [
        (90.0, 100.0, 'O', 10),
        (80.0, 89.99, 'A+', 9),
        (70.0, 79.99, 'A', 8),
        (60.0, 69.99, 'B+', 7),
        (55.0, 59.99, 'B', 6),
        (50.0, 54.99, 'C', 5),
        (40.0, 49.99, 'P', 4),
        (0.0, 39.99, 'F', 0)
    ]
    cursor.executemany(
        "INSERT INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)",
        new_rules
    )


def get_grade_from_percentage(cursor, percentage):
    """Get grade and grade_point based on percentage using NEW grading rules"""
    cursor.execute(
        "SELECT grade, grade_point FROM grading_rules WHERE ? BETWEEN min_percentage AND max_percentage",
        (percentage,)
    )
    result = cursor.fetchone()
    if result:
        return result[0], result[1]
    else:
        return 'F', 0.0  # Fallback


def migrate_database(old_db_path, output_path='migrated_database.db'):
    """
    Migrate old database to new schema
    
    Args:
        old_db_path: Path to old database backup
        output_path: Path for migrated database (default: migrated_database.db)
    """
    
    print(f"🔄 Starting migration from: {old_db_path}")
    print(f"📦 Output will be saved to: {output_path}")
    
    # Check if old database exists
    if not os.path.exists(old_db_path):
        print(f"❌ Error: File not found: {old_db_path}")
        return False
    
    # Connect to old database
    print("\n📖 Reading old database...")
    old_conn = sqlite3.connect(old_db_path)
    old_cursor = old_conn.cursor()
    
    # Read all data from old database
    try:
        users = old_cursor.execute("SELECT * FROM users").fetchall()
        presets = old_cursor.execute("SELECT * FROM presets").fetchall()
        subjects = old_cursor.execute("SELECT * FROM subjects").fetchall()
        components = old_cursor.execute("SELECT * FROM components").fetchall()
        student_marks = old_cursor.execute("SELECT * FROM student_marks").fetchall()
        subject_results = old_cursor.execute("SELECT * FROM subject_results").fetchall()
        cgpa_records = old_cursor.execute("SELECT * FROM cgpa").fetchall()
        
        print(f"   ✓ Found {len(users)} users")
        print(f"   ✓ Found {len(presets)} presets")
        print(f"   ✓ Found {len(subjects)} subjects")
        print(f"   ✓ Found {len(components)} components")
        print(f"   ✓ Found {len(student_marks)} student marks")
        print(f"   ✓ Found {len(subject_results)} subject results")
        print(f"   ✓ Found {len(cgpa_records)} CGPA records")
        
    except sqlite3.Error as e:
        print(f"❌ Error reading old database: {e}")
        old_conn.close()
        return False
    
    old_conn.close()
    
    # Create new database with new schema
    print("\n🔨 Creating new database with updated schema...")
    if os.path.exists(output_path):
        os.remove(output_path)
    
    new_conn = sqlite3.connect(output_path)
    new_cursor = new_conn.cursor()
    
    create_new_schema(new_cursor)
    print("   ✓ New schema created")
    
    # Migrate data
    print("\n📝 Migrating data...")
    
    # 1. Users (no conversion needed)
    if users:
        new_cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?)", users)
        print(f"   ✓ Migrated {len(users)} users")
    
    # 2. Presets (no conversion needed)
    if presets:
        new_cursor.executemany("INSERT INTO presets VALUES (?, ?, ?, ?, ?, ?)", presets)
        print(f"   ✓ Migrated {len(presets)} presets")
    
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
        new_cursor.executemany("INSERT INTO student_marks VALUES (?, ?, ?, ?)", converted_marks)
        print(f"   ✓ Migrated {len(student_marks)} student marks (converted to REAL)")
    
    # 6. Subject results (recalculate grades with new rules)
    if subject_results:
        recalculated = 0
        for result in subject_results:
            id, user_id, subject_id, total_obtained, total_max, percentage, old_grade, old_grade_point = result
            
            # Get new grade based on percentage using NEW grading rules
            new_grade, new_grade_point = get_grade_from_percentage(new_cursor, percentage)
            
            # Insert with new grade and grade_point
            new_cursor.execute(
                "INSERT INTO subject_results VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
        new_cursor.executemany("INSERT INTO cgpa VALUES (?, ?, ?)", cgpa_records)
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
