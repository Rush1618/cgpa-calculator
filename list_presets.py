import sqlite3

def list_presets():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets")
    presets = cursor.fetchall()
    conn.close()
    
    print(f"{'ID':<4} | {'Ac Year':<10} | {'Course':<10} | {'Dept':<20} | {'Yr':<4} | {'Div':<4} | {'Sem':<4}")
    print("-" * 80)
    for p in presets:
        print(f"{p[0]:<4} | {p[1]:<10} | {p[2]:<10} | {p[3] if p[3] else 'None':<20} | {p[4]:<4} | {p[5]:<4} | {p[6]:<4}")

if __name__ == "__main__":
    list_presets()
