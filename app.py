from flask import Flask, redirect, url_for, render_template, session, request, flash, send_file
from authlib.integrations.flask_client import OAuth
import os
from datetime import datetime
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


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

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
                "INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)",
                (user_info['email'], user_info.get('name', 'Unknown'), is_admin)
            )
            conn.commit()
        else:
            # User exists, update their admin status if necessary
            # Assuming is_admin is the 5th column (index 4)
            current_is_admin = user[4] 
            expected_is_admin = 1 if user_info['email'] == ADMIN_EMAIL else 0
            if current_is_admin != expected_is_admin:
                cursor.execute(
                    "UPDATE users SET is_admin = ? WHERE email = ?",
                    (expected_is_admin, user_info['email'])
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

        return redirect(url_for('student_dashboard'))

    return render_template('additional_info.html')


@app.route('/admin/db/download')
def download_db():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))
    
    try:
        return send_file('database.db', as_attachment=True)
    except Exception as e:
        flash(f"Error downloading database: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/db/upload', methods=['POST'])
def upload_db():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))
    
    if 'db_file' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('admin_dashboard'))
    
    file = request.files['db_file']
    
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if file:
        try:
            # Save the file, overwriting the existing database.db
            # Warning: This is a destructive operation!
            file.save('database.db')
            flash('Database restored successfully! Please refresh or restart if needed.', 'success')
        except Exception as e:
            flash(f"Error restoring database: {str(e)}", "error")
            
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/presets/edit/<int:preset_id>', methods=['POST'])
def edit_preset(preset_id):
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
        "UPDATE presets SET academic_year=?, course=?, year=?, division=?, semester=? WHERE id=?",
        (academic_year, course, year, division, semester, preset_id)
    )
    conn.commit()
    conn.close()

    flash('Preset updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/presets/duplicate/<int:preset_id>', methods=['POST'])
def duplicate_preset(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    # 1. Create the NEW Preset
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
    new_preset_id = cursor.lastrowid

    # 2. Fetch Original Subjects
    cursor.execute("SELECT * FROM subjects WHERE preset_id=?", (preset_id,))
    original_subjects = cursor.fetchall()

    # 3. Copy Subjects & Components
    for subj in original_subjects:
        # subj: (id, preset_id, name, code, credits)
        cursor.execute(
            "INSERT INTO subjects (preset_id, name, code, credits) VALUES (?, ?, ?, ?)",
            (new_preset_id, subj[2], subj[3], subj[4])
        )
        new_subject_id = cursor.lastrowid
        
        # Fetch Components for this subject
        cursor.execute("SELECT * FROM components WHERE subject_id=?", (subj[0],))
        components = cursor.fetchall()
        
        # Copy Components
        for comp in components:
            # comp: (id, subject_id, name, max_marks)
            cursor.execute(
                "INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)",
                (new_subject_id, comp[2], comp[3])
            )

    conn.commit()
    conn.close()

    flash(f'Preset cloned successfully! Created {len(original_subjects)} subjects.', 'success')
    return redirect(url_for('admin_dashboard'))


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

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        action = request.form.get('action')

        academic_year = request.form['academic_year']
        course = request.form['course']
        year = request.form['year']
        division = request.form['division']
        semester = request.form['semester']

        cursor.execute(
            "SELECT id FROM presets WHERE academic_year=? AND course=? AND year=? AND division=? AND semester=?",
            (academic_year, course, year, division, semester)
        )
        preset = cursor.fetchone()

        if action == 'load_subjects':
            if not preset:
                # Fetch options again to re-render dropdowns
                cursor.execute("SELECT DISTINCT academic_year FROM presets")
                academic_years = [row[0] for row in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT course FROM presets")
                courses = [row[0] for row in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT year FROM presets")
                years = [row[0] for row in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT division FROM presets")
                divisions = [row[0] for row in cursor.fetchall()]

                cursor.execute("SELECT DISTINCT semester FROM presets")
                semesters = [row[0] for row in cursor.fetchall()]
                conn.close()

                return render_template('student.html', preset_not_found=True,
                                       academic_years=academic_years, courses=courses,
                                       years=years, divisions=divisions, semesters=semesters)

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
            
            if not subject_ids:
                 flash("No subjects selected/found.", "error")
                 return redirect(url_for('student_dashboard'))

            total_credits = 0
            total_weighted_points = 0
            
            try:
                for subject_id in subject_ids:
                    cursor.execute("SELECT credits FROM subjects WHERE id=?", (subject_id,))
                    res_credits = cursor.fetchone()
                    if not res_credits: continue # Skip if bad subject ID
                    credits = res_credits[0]

                    cursor.execute("SELECT id, max_marks FROM components WHERE subject_id=?", (subject_id,))
                    components = cursor.fetchall()

                    total_obtained = 0
                    total_max = 0

                    for comp_id, max_marks in components:
                        marks_str = request.form.get(f'marks_{comp_id}', '0')
                        if not marks_str.isdigit(): marks_str = '0'
                        marks = int(marks_str)
                        
                        total_obtained += marks
                        total_max += max_marks

                        cursor.execute(
                            "INSERT OR REPLACE INTO student_marks (user_id, component_id, marks_obtained) VALUES (?, ?, ?)",
                            (user_id, comp_id, marks)
                        )
                    
                    if total_max > 0:
                        percentage = (total_obtained / total_max) * 100
                    else:
                        percentage = 0

                    cursor.execute(
                        "SELECT grade, grade_point FROM grading_rules WHERE ? BETWEEN min_percentage AND max_percentage",
                        (percentage,)
                    )
                    grade_res = cursor.fetchone()
                    
                    if grade_res:
                        grade, grade_point = grade_res
                    else:
                        # Fallback if no rule matches
                        grade, grade_point = 'F', 0.0

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
            except Exception as e:
                print(f"Error calculating CGPA: {e}")
                conn.rollback()
                flash("An error occurred during calculation. Please check your inputs.", "error")
                return redirect(url_for('student_dashboard'))
                
            conn.close()

            return redirect(url_for('view_result'))

    # GET request: Fetch options for dropdowns
    cursor.execute("SELECT DISTINCT academic_year FROM presets")
    academic_years = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT course FROM presets")
    courses = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT year FROM presets")
    years = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT division FROM presets")
    divisions = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT semester FROM presets")
    semesters = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template(
        'student.html',
        academic_years=academic_years,
        courses=courses,
        years=years,
        divisions=divisions,
        semesters=semesters
    )


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


@app.route('/admin/students/<int:user_id>/marks')
def view_student_marks(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()

    # Get Subject Results (Overview)
    cursor.execute("""
        SELECT s.name, s.code, s.credits, sr.total_obtained, sr.total_max, sr.percentage, sr.grade, sr.grade_point, s.id
        FROM subject_results sr
        JOIN subjects s ON sr.subject_id = s.id
        WHERE sr.user_id = ?
    """, (user_id,))
    subject_results = cursor.fetchall()

    # Get Detailed Component Marks
    detailed_marks = {}
    for res in subject_results:
        subject_id = res[8] # the s.id selected at the end
        cursor.execute("""
            SELECT c.name, sm.marks_obtained, c.max_marks
            FROM student_marks sm
            JOIN components c ON sm.component_id = c.id
            WHERE sm.user_id = ? AND c.subject_id = ?
        """, (user_id, subject_id))
        detailed_marks[subject_id] = cursor.fetchall()

    # Get Final CGPA
    cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
    cgpa_data = cursor.fetchone()
    cgpa = cgpa_data[0] if cgpa_data else 0

    conn.close()

    return render_template(
        'admin_student_results.html',
        student=student,
        subject_results=subject_results,
        detailed_marks=detailed_marks,
        cgpa=cgpa
    )


@app.route('/admin/students/<int:user_id>/download_csv')
def download_student_csv(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    import csv
    import io

    conn = create_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT name, roll_number, email FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()
    student_name = student[0]

    # Get Marks Data
    cursor.execute("""
        SELECT s.name, s.code, c.name, sm.marks_obtained, c.max_marks
        FROM student_marks sm
        JOIN components c ON sm.component_id = c.id
        JOIN subjects s ON c.subject_id = s.id
        WHERE sm.user_id = ?
        ORDER BY s.name, c.name
    """, (user_id,))
    marks_data = cursor.fetchall()
    
    # Get Result Data
    cursor.execute("""
        SELECT s.name, sr.percentage, sr.grade, sr.grade_point
        FROM subject_results sr
        JOIN subjects s ON sr.subject_id = s.id
        WHERE sr.user_id = ?
    """, (user_id,))
    results_data = cursor.fetchall()
    
    cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
    cgpa_row = cursor.fetchone()
    cgpa = cgpa_row[0] if cgpa_row else "N/A"

    conn.close()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Student Report'])
    writer.writerow(['Name', student[0]])
    writer.writerow(['Roll Number', student[1]])
    writer.writerow(['Email', student[2]])
    writer.writerow(['SGPA/CGPA', cgpa])
    writer.writerow([])
    
    writer.writerow(['--- Detailed Component Marks ---'])
    writer.writerow(['Subject', 'Code', 'Component', 'Obtained', 'Max'])
    for row in marks_data:
        writer.writerow(row)
    
    writer.writerow([])
    writer.writerow(['--- Subject Grades ---'])
    writer.writerow(['Subject', 'Percentage', 'Grade', 'Grade Point'])
    for row in results_data:
        writer.writerow(row)

    output.seek(0)
    
    # Using 'send_file' with BytesIO would be better but StringIO works if we encode
    # Alternatively send_file expects bytes usually or a path. 
    # Let's use make_response to just send the string as csv
    from flask import make_response
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=result_{student_name}.csv"
    response.headers["Content-type"] = "text/csv"
    return response



@app.route('/admin/master_sheet')
def master_sheet():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    # Fetch all presets for the filter dropdown
    cursor.execute("SELECT * FROM presets")
    presets = cursor.fetchall()

    selected_preset_id = request.args.get('preset_id')
    
    table_headers = []
    students_data = []
    subjects = []

    if selected_preset_id:
        # Get Preset Info
        cursor.execute("SELECT * FROM presets WHERE id=?", (selected_preset_id,))
        preset = cursor.fetchone()

        # 1. Get Subjects (Columns)
        cursor.execute("SELECT id, name, code, credits FROM subjects WHERE preset_id=?", (selected_preset_id,))
        subjects = cursor.fetchall()
        
        # Prepare headers: Name, Roll, [Sub1, Sub2...], SGPA/CGPA
        table_headers = ['Roll Number', 'Name'] + [s[1] for s in subjects] + ['SGPA/CGPA']
        
        # 2. Find students who have taken these subjects
        if subjects:
            subject_ids = tuple([s[0] for s in subjects])
            # Handle case with 1 subject
            if len(subject_ids) == 1:
                query_condition = f"({subject_ids[0]})"
            else:
                query_condition = str(subject_ids)
            
            query = f"""
                SELECT DISTINCT u.id, u.name, u.roll_number 
                FROM users u
                JOIN subject_results sr ON u.id = sr.user_id
                WHERE sr.subject_id IN {query_condition}
                ORDER BY u.roll_number
            """
            cursor.execute(query)
            students = cursor.fetchall()

            # 3. Build Row Data
            for student in students:
                user_id = student[0]
                row = {
                    'roll': student[2],
                    'name': student[1],
                    'marks': {},
                    'cgpa': 0
                }

                # Fetch marks for each subject
                for sub in subjects:
                    sub_id = sub[0]
                    cursor.execute("""
                        SELECT percentage, grade, grade_point 
                        FROM subject_results 
                        WHERE user_id=? AND subject_id=?
                    """, (user_id, sub_id))
                    res = cursor.fetchone()
                    if res:
                        row['marks'][sub_id] = f"{res[1]} ({int(res[0])}%)"
                    else:
                        row['marks'][sub_id] = "-"
                
                # Fetch CGPA
                cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
                cgpa_res = cursor.fetchone()
                row['cgpa'] = "%.2f" % cgpa_res[0] if cgpa_res else "-"
                
                students_data.append(row)

    conn.close()

    return render_template('master_sheet.html', 
                           presets=presets, 
                           selected_preset_id=int(selected_preset_id) if selected_preset_id else None,
                           headers=table_headers,
                           subjects=subjects,
                           students_data=students_data)


@app.route('/admin/master_sheet/download')
def download_master_csv():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))
    
    selected_preset_id = request.args.get('preset_id')
    if not selected_preset_id:
        flash("Please select a class first.", "error")
        return redirect(url_for('master_sheet'))

    import csv
    import io
    from flask import make_response

    conn = create_connection()
    cursor = conn.cursor()
    
    # Logic mirrors master_sheet but writes to CSV
    cursor.execute("SELECT * FROM presets WHERE id=?", (selected_preset_id,))
    preset = cursor.fetchone()
    # preset name for filename
    preset_name = f"{preset[2]}_{preset[3]}Yr_{preset[4]}".replace(" ", "_")

    cursor.execute("SELECT id, name, code, credits FROM subjects WHERE preset_id=?", (selected_preset_id,))
    subjects = cursor.fetchall()

    subject_ids = tuple([s[0] for s in subjects])
    if len(subject_ids) == 1:
        query_condition = f"({subject_ids[0]})"
    else:
        query_condition = str(subject_ids)
    
    query = f"""
        SELECT DISTINCT u.id, u.name, u.roll_number 
        FROM users u
        JOIN subject_results sr ON u.id = sr.user_id
        WHERE sr.subject_id IN {query_condition}
        ORDER BY u.roll_number
    """
    cursor.execute(query)
    students = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    headers = ['Roll Number', 'Name'] + [f"{s[1]} (Grade)" for s in subjects] + ['SGPA/CGPA']
    writer.writerow(headers)

    for student in students:
        user_id = student[0]
        row_data = [student[2], student[1]] # Roll, Name

        for sub in subjects:
            sub_id = sub[0]
            cursor.execute("SELECT percentage, grade FROM subject_results WHERE user_id=? AND subject_id=?", (user_id, sub_id))
            res = cursor.fetchone()
            if res:
                row_data.append(f"{res[1]} ({int(res[0])}%)")
            else:
                row_data.append("-")
        
        cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
        cgpa_res = cursor.fetchone()
        row_data.append("%.2f" % cgpa_res[0] if cgpa_res else "-")

        writer.writerow(row_data)

    conn.close()
    
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=MasterSheet_{preset_name}.csv"
    response.headers["Content-type"] = "text/csv"
    return response
def download_pdf():
    if 'user' not in session:
        return redirect(url_for('index'))

    flash("PDF generation coming soon!", "info")
    return redirect(url_for('view_result'))

if __name__ == '__main__':
    app.run(debug=True)