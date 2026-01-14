from flask import Flask, redirect, url_for, render_template, session, request, flash
from authlib.integrations.flask_client import OAuth
import os
from database import create_connection
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# Ensure database tables are created
from database import create_tables
create_tables()

oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

ADMIN_EMAIL = "singh02.rushabh@gmail.com"


@app.route('/')
def index():
    if 'user' in session:
        user_info = session['user']
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (user_info['email'],))
        user = cursor.fetchone()
        conn.close()

        if user and user[2] and user[3]:
            if user_info['email'] == ADMIN_EMAIL:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('additional_info'))

    return render_template('login.html')


@app.route('/login')
def login():
    return google.authorize_redirect(url_for('authorize', _external=True))


@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = google.get(google.server_metadata.get('userinfo_endpoint')).json()
        session['user'] = user_info

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (user_info['email'],))
        user = cursor.fetchone()

        if not user:
            is_admin = 1 if user_info['email'] == ADMIN_EMAIL else 0
            cursor.execute(
                "INSERT INTO users (email, is_admin) VALUES (?, ?)",
                (user_info['email'], is_admin)
            )
            conn.commit()

        conn.close()
        return redirect('/')

    except Exception as e:
        return f"OAuth Error: {str(e)}", 400


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


@app.route('/additional_info', methods=['GET', 'POST'])
def additional_info():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET name = ?, roll_number = ? WHERE email = ?",
            (name, roll_number, session['user']['email'])
        )
        conn.commit()
        conn.close()

        return redirect('/')

    return render_template('additional_info.html')


@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM presets")
    presets = cursor.fetchall()
    conn.close()
    return render_template('admin.html', presets=presets)
@app.route('/admin/presets/add', methods=['POST'])
def add_preset():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    academic_year = request.form['academic_year']
    course = request.form['course']
    year = request.form['year']
    division = request.form['division']
    semester = request.form['semester']

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO presets (academic_year, course, year, division, semester) VALUES (?, ?, ?, ?, ?)",
        (academic_year, course, year, division, semester)
    )
    conn.commit()
    conn.close()

    flash('Preset added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/student', methods=['GET', 'POST'])
def student_dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        action = request.form.get('action')

        academic_year = request.form['academic_year']
        course = request.form['course']
        year = request.form['year']
        division = request.form['division']
        semester = request.form['semester']

        conn = create_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM presets WHERE academic_year=? AND course=? AND year=? AND division=? AND semester=?",
            (academic_year, course, year, division, semester)
        )
        preset = cursor.fetchone()

        if action == 'load_subjects':
            if not preset:
                conn.close()
                return render_template('student.html', preset_not_found=True)

            preset_id = preset[0]
            cursor.execute("SELECT * FROM subjects WHERE preset_id=?", (preset_id,))
            subjects = cursor.fetchall()

            subject_components = {}
            for s in subjects:
                cursor.execute("SELECT * FROM components WHERE subject_id=?", (s[0],))
                subject_components[s[0]] = cursor.fetchall()

            conn.close()
            return render_template(
                'student.html',
                subjects=subjects,
                subject_components=subject_components,
                academic_year=academic_year,
                course=course,
                year=year,
                division=division,
                semester=semester
            )

        elif action == 'calculate_cgpa':
            user_email = session['user']['email']
            cursor.execute("SELECT id FROM users WHERE email=?", (user_email,))
            user_id = cursor.fetchone()[0]

            subject_ids = request.form.getlist('subjects')

            total_credits = 0
            total_weighted_points = 0

            for subject_id in subject_ids:
                cursor.execute("SELECT credits FROM subjects WHERE id=?", (subject_id,))
                credits = cursor.fetchone()[0]

                cursor.execute("SELECT id, max_marks FROM components WHERE subject_id=?", (subject_id,))
                components = cursor.fetchall()

                total_obtained = 0
                total_max = 0

                for comp_id, max_marks in components:
                    marks = int(request.form[f'marks_{comp_id}'])
                    total_obtained += marks
                    total_max += max_marks

                    cursor.execute(
                        "INSERT OR REPLACE INTO student_marks (user_id, component_id, marks_obtained) VALUES (?, ?, ?)",
                        (user_id, comp_id, marks)
                    )

                percentage = (total_obtained / total_max) * 100

                cursor.execute(
                    "SELECT grade, grade_point FROM grading_rules WHERE ? BETWEEN min_percentage AND max_percentage",
                    (percentage,)
                )
                grade, grade_point = cursor.fetchone()

                total_credits += credits
                total_weighted_points += grade_point * credits

                cursor.execute(
                    "INSERT OR REPLACE INTO subject_results (user_id, subject_id, total_obtained, total_max, percentage, grade, grade_point) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (user_id, subject_id, total_obtained, total_max, percentage, grade, grade_point)
                )

            cgpa = total_weighted_points / total_credits if total_credits else 0

            cursor.execute(
                "INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)",
                (user_id, cgpa)
            )

            conn.commit()
            conn.close()

            return redirect(url_for('view_result'))

    return render_template('student.html')


@app.route('/result')
def view_result():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email=?", (session['user']['email'],))
    user_id = cursor.fetchone()[0]

    cursor.execute("""
        SELECT s.name, sr.total_obtained, sr.total_max, sr.percentage, sr.grade, sr.grade_point
        FROM subject_results sr
        JOIN subjects s ON sr.subject_id = s.id
        WHERE sr.user_id = ?
    """, (user_id,))
    subject_results = cursor.fetchall()

    cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
    cgpa = cursor.fetchone()

    conn.close()

    return render_template('result.html', subject_results=subject_results, cgpa=cgpa)


@app.route('/admin/students')
def view_students():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_number, email FROM users WHERE is_admin=0")
    students = cursor.fetchall()
    conn.close()

    return render_template('view_students.html', students=students)


@app.route('/admin/grading_rules', methods=['GET', 'POST'])
def manage_grading_rules():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        rule_ids = request.form.getlist('rule_id')
        mins = request.form.getlist('min_percentage')
        maxs = request.form.getlist('max_percentage')
        grades = request.form.getlist('grade')
        points = request.form.getlist('grade_point')

        for i in range(len(rule_ids)):
            cursor.execute(
                "UPDATE grading_rules SET min_percentage=?, max_percentage=?, grade=?, grade_point=? WHERE id=?",
                (mins[i], maxs[i], grades[i], points[i], rule_ids[i])
            )

        conn.commit()

    cursor.execute("SELECT * FROM grading_rules")
    rules = cursor.fetchall()
    conn.close()

    return render_template('manage_grading_rules.html', rules=rules)


@app.route('/admin/presets/<int:preset_id>/subjects')
def manage_subjects(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM presets WHERE id=?", (preset_id,))
    preset = cursor.fetchone()

    cursor.execute("SELECT * FROM subjects WHERE preset_id=?", (preset_id,))
    subjects = cursor.fetchall()

    subject_components = {}
    for subject in subjects:
        cursor.execute("SELECT * FROM components WHERE subject_id=?", (subject[0],))
        subject_components[subject[0]] = cursor.fetchall()

    conn.close()

    return render_template(
        'manage_subjects.html',
        preset=preset,
        subjects=subjects,
        subject_components=subject_components
    )


@app.route('/admin/presets/<int:preset_id>/subjects/add', methods=['POST'])
def add_subject(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    name = request.form['name']
    code = request.form['code']
    credits = request.form['credits']
    components = request.form.getlist('components')

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO subjects (preset_id, name, code, credits) VALUES (?, ?, ?, ?)",
        (preset_id, name, code, credits)
    )
    subject_id = cursor.lastrowid

    for comp in components:
        max_marks = request.form.get(f'max_marks_{comp}')
        cursor.execute(
            "INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)",
            (subject_id, comp, max_marks)
        )

    conn.commit()
    conn.close()

    flash("Subject added successfully!", "success")
    return redirect(url_for('manage_subjects', preset_id=preset_id))


@app.route('/admin/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT preset_id FROM subjects WHERE id=?", (subject_id,))
    preset_id = cursor.fetchone()[0]

    cursor.execute("DELETE FROM components WHERE subject_id=?", (subject_id,))
    cursor.execute("DELETE FROM subjects WHERE id=?", (subject_id,))

    conn.commit()
    conn.close()

    flash("Subject deleted!", "success")
    return redirect(url_for('manage_subjects', preset_id=preset_id))


@app.route('/admin/students/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_student_record(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']

        cursor.execute(
            "UPDATE users SET name=?, roll_number=? WHERE id=?",
            (name, roll_number, user_id)
        )

        conn.commit()
        conn.close()

        flash("Student updated!", "success")
        return redirect(url_for('view_students'))

    cursor.execute("SELECT name, roll_number FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()

    conn.close()
    return render_template('edit_student_record.html', student=student, user_id=user_id)


@app.route('/admin/students/delete/<int:user_id>')
def delete_student_record(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM student_marks WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM subject_results WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM cgpa WHERE user_id=?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))

    conn.commit()
    conn.close()

    flash("Student deleted!", "success")
    return redirect(url_for('view_students'))


@app.route('/download_pdf')
def download_pdf():
    if 'user' not in session:
        return redirect(url_for('index'))

    flash("PDF generation coming soon!", "info")
    return redirect(url_for('view_result'))

if __name__ == '__main__':
    app.run(debug=True)