import sqlite3

def create_connection():
    conn = sqlite3.connect('database.db')
    return conn

def create_tables():
    conn = create_connection()
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            roll_number TEXT,
            is_admin BOOLEAN DEFAULT 0
        )
    """)

    # Create presets table
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

    # Create subjects table
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

    # Create components table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS components (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            max_marks INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (id)
        )
    """)

    # Create student_marks table
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

    # Create subject_results table
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

    # Create cgpa table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cgpa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            cgpa REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Create grading_rules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS grading_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            min_percentage REAL NOT NULL,
            max_percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            grade_point REAL NOT NULL
        )
    """)

    # Insert default grading rules (matching official university system)
    cursor.execute("SELECT COUNT(*) FROM grading_rules")
    if cursor.fetchone()[0] == 0:
        default_rules = [
            (90.0, 100.0, 'O', 10),      # Outstanding: 90-100%
            (80.0, 89.99, 'A+', 9),      # Excellent: 80-<90%
            (70.0, 79.99, 'A', 8),       # Very Good: 70-<80%
            (60.0, 69.99, 'B+', 7),      # Good: 60-<70%
            (55.0, 59.99, 'B', 6),       # Above Average: 55-<60%
            (50.0, 54.99, 'C', 5),       # Average: 50-<55%
            (40.0, 49.99, 'P', 4),       # Pass: 40-<50%
            (0.0, 39.99, 'F', 0)         # Fail: 0-<40%
        ]
        cursor.executemany("INSERT INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)", default_rules)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_tables()
