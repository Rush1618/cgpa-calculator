import sqlite3

def recalculate_grades():
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Fetching new grading rules...")
    cursor.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
    rules = cursor.fetchall()
    
    # 1. Update Subject Results (Grades & Pointers)
    print("Recalculating Subject Grades...")
    cursor.execute("SELECT id, user_id, subject_id, total_obtained, total_max FROM subject_results")
    results = cursor.fetchall()
    
    updated_count = 0
    for res_id, user_id, subject_id, obtained, max_marks in results:
        if max_marks <= 0:
            percentage = 0
        else:
            percentage = (obtained / max_marks) * 100
        
        # Find new grade
        new_grade = 'F'
        new_point = 0.0
        
        for min_p, max_p, grade, point in rules:
            # Using precise comparison as per typical logic, float tolerance is handled by range
            if percentage >= min_p and percentage <= max_p:
                new_grade = grade
                new_point = point
                break
        
        cursor.execute(
            "UPDATE subject_results SET percentage=?, grade=?, grade_point=? WHERE id=?",
            (percentage, new_grade, new_point, res_id)
        )
        updated_count += 1
        
    print(f"Updated {updated_count} subject results.")
    conn.commit()
    conn.close()
    print("Recalculation Complete.")

if __name__ == "__main__":
    recalculate_grades()
