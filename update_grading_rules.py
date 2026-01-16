import sqlite3

def update_grading_rules():
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing rules
    print("Clearing existing grading rules...")
    cursor.execute("DELETE FROM grading_rules")

    # New Rules based on user image
    # Note: Ranges are handled as min inclusive, max inclusive in logic usually, 
    # but let's be precise with decimals to mimic "< 90" etc.
    rules = [
        (90.0, 100.0, 'O', 10.0),
        (80.0, 89.99, 'A+', 9.0),
        (70.0, 79.99, 'A', 8.0),
        (60.0, 69.99, 'B+', 7.0),
        (55.0, 59.99, 'B', 6.0),
        (50.0, 54.99, 'C', 5.0),
        (40.0, 49.99, 'P', 4.0),
        (0.0, 39.99, 'F', 0.0)
    ]

    print("Inserting new grading rules...")
    cursor.executemany(
        "INSERT INTO grading_rules (min_percentage, max_percentage, grade, grade_point) VALUES (?, ?, ?, ?)",
        rules
    )

    conn.commit()
    
    # Verify
    cursor.execute("SELECT * FROM grading_rules ORDER BY grade_point DESC")
    print("\nNew Grading Rules:")
    for row in cursor.fetchall():
        print(row)

    conn.close()
    print("\nGrading rules updated successfully.")

if __name__ == "__main__":
    update_grading_rules()
