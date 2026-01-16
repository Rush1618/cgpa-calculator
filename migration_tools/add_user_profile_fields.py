import sqlite3
import os

def migrate():
    # Path relative to this script: ../database.db
    db_path = os.path.join(os.path.dirname(__file__), '..', 'database.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    columns = [
        ('enrollment_number', 'TEXT'),
        ('department', 'TEXT'),
        ('academic_year', 'TEXT'),
        ('current_year', 'TEXT')
    ]

    print(f"Connecting to database at {db_path}")

    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [row[1] for row in cursor.fetchall()]

    for col_name, col_type in columns:
        if col_name not in existing_columns:
            print(f"Adding column {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                print(f"Added {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column {col_name} already exists.")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
