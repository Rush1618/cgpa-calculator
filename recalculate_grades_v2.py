import sqlite3

def recalculate_grades_v2():
    db_path = 'database.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Fetching new grading rules...")
    cursor.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
    rules = cursor.fetchall()
    
    # 1. Update Subject Results (Grades & Pointers)
    print("Recalculating Subject Grades...")
    # Based on PRAGMA output, columns are: user_id, subject_id, total_obtained_marks, total_max_marks
    cursor.execute("SELECT user_id, subject_id, total_obtained_marks, total_max_marks FROM subject_results")
    results = cursor.fetchall()
    
    updated_count = 0
    for user_id, subject_id, obtained, max_marks in results:
        if max_marks is None or max_marks <= 0:
            percentage = 0
        else:
            percentage = (obtained / max_marks) * 100
        
        # Find new grade
        new_grade = 'F'
        new_point = 0.0
        
        for min_p, max_p, grade, point in rules:
            if percentage >= min_p and percentage <= max_p:
                new_grade = grade
                new_point = point
                break
        
        # Update using composite key (user_id, subject_id)
        cursor.execute(
            "UPDATE subject_results SET percentage=?, grade=?, grade_point=? WHERE user_id=? AND subject_id=?",
            (percentage, new_grade, new_point, user_id, subject_id)
        )
        updated_count += 1
        
    print(f"Updated {updated_count} subject results.")
    conn.commit()
    conn.close()
    print("Recalculation Complete.")

if __name__ == "__main__":
    recalculate_grades_v2()
