import sqlite3

def find_presets():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets")
    presets = cursor.fetchall()
    conn.close()
    
    print("\n--- Listing All Presets ---")
    for p in presets:
        # 0:id, 1:ac_year, 2:course, 3:dept, 4:year, 5:div, 6:sem
        print(f"ID: {p[0]}, Dept: {p[3]}, Year: {p[4]}, Div: {p[5]}, Sem: {p[6]} . Full: {p}")

    print("\n--- Candidates for Source ---")
    # "2025-2026 - BE Computer Engineering (Computer Engineering Yr, Div SE, Sem A)"
    # Likely: Year=SE, Div=A. Sem=?? User said "Sem A"? Maybe Sem=3?
    for p in presets:
        if p[1] == '2025-2026' and p[4] == 'SE' and p[5] == 'A':
            print(f"SOURCE CANDIDATE: ID {p[0]} (Sem {p[6]})")

    print("\n--- Candidates for Target ---")
    # "department of co sem 3" -> Dept='Computer Engineering', Sem='3'
    for p in presets:
        if (p[3] == 'Computer Engineering' or p[3] == 'CO') and str(p[6]) == '3':
            print(f"TARGET CANDIDATE: ID {p[0]} (Year {p[4]}, Div {p[5]})")

if __name__ == "__main__":
    find_presets()
