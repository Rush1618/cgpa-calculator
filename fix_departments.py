import sqlite3

def fix_departments():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # 1. Update Presets
    print("Updating Presets...")
    cursor.execute("UPDATE presets SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    print(f"Updated {cursor.rowcount} Chemical -> Mechanical presets.")

    cursor.execute("UPDATE presets SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    print(f"Updated {cursor.rowcount} EXTC -> ECS presets.")
    
    # 2. Update Users
    print("\nUpdating Users...")
    cursor.execute("UPDATE users SET department = 'Mechanical Engineering' WHERE department = 'Chemical Engineering'")
    print(f"Updated {cursor.rowcount} Chemical -> Mechanical users.")

    cursor.execute("UPDATE users SET department = 'Electronics & Computer Science' WHERE department = 'Electronics & Telecom'")
    print(f"Updated {cursor.rowcount} EXTC -> ECS users.")

    conn.commit()
    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    fix_departments()
