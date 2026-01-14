from flask import Flask, redirect, url_for, render_template, session, request, flash, jsonify
import os
import firebase_admin
from firebase_admin import credentials, auth
from dotenv import load_dotenv, find_dotenv
from database import create_connection # Import from database.py

# Load environment variables from .env file in the cgpa_system directory
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Firebase Admin SDK Initialization
# IMPORTANT: Replace 'path/to/your/serviceAccountKey.json' with the actual path to your Firebase service account key.
# You can download this file from your Firebase project settings -> Service accounts.
# Make sure this file is placed securely and its path is correct.
SERVICE_ACCOUNT_KEY_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY_PATH", 'path/to/your/serviceAccountKey.json')

try:
    if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    else:
        print(f"WARNING: Firebase service account key not found at {SERVICE_ACCOUNT_KEY_PATH}.")
        print("Firebase authentication will not work correctly on the backend.")
        print("Please download your service account key and update FIREBASE_SERVICE_ACCOUNT_KEY_PATH in .env or app.py.")
except Exception as e:
    print(f"Error initializing Firebase Admin SDK: {e}")

ADMIN_EMAIL = "singh02.rushabh@gmail.com"

# Utility function to get firebase config for frontend
def get_firebase_config():
    return {
        "apiKey": os.getenv("VITE_FIREBASE_API_KEY"),
        "authDomain": os.getenv("VITE_FIREBASE_AUTH_DOMAIN"),
        "projectId": os.getenv("VITE_FIREBASE_PROJECT_ID"),
        "storageBucket": os.getenv("VITE_FIREBASE_STORAGE_BUCKET"),
        "messagingSenderId": os.getenv("VITE_FIREBASE_MESSAGING_SENDER_ID"),
        "appId": os.getenv("VITE_FIREBASE_APP_ID"),
        "measurementId": os.getenv("VITE_FIREBASE_MEASUREMENT_ID")
    }

@app.route('/')
def index():
    if 'user' in session:
        user_info = session['user']
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (user_info['email'],))
        user = cursor.fetchone()
        conn.close()

        if user and user[2] and user[3]: # Check if name and roll number are filled
            if user_info['email'] == ADMIN_EMAIL:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            return redirect(url_for('additional_info'))

    # If no user in session, render login.html and pass firebase_config
    return render_template('login.html', firebase_config=get_firebase_config())

@app.route('/login')
def login():
    # Pass Firebase client-side configuration to the template
    return render_template('login.html', firebase_config=get_firebase_config())

@app.route('/verify-token', methods=['POST'])
def verify_token():
    id_token = request.json.get('idToken')
    if not id_token:
        return jsonify({'message': 'ID Token not provided'}), 400

    try:
        # Verify the ID token using the Firebase Admin SDK.
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token['email']
        name = decoded_token.get('name', '')

        session['user'] = {
            'uid': uid,
            'email': email,
            'name': name
        }

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if not user:
            is_admin = 1 if email == ADMIN_EMAIL else 0
            cursor.execute("INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)", (email, name, is_admin))
            conn.commit()
        elif not user[2]: # If name is not yet set in our DB, update it
            cursor.execute("UPDATE users SET name = ? WHERE email = ?", (name, email))
            conn.commit()
        conn.close()
        
        return jsonify({'message': 'Authentication successful'}), 200

    except auth.InvalidIdTokenError:
        return jsonify({'message': 'Invalid ID Token'}), 401
    except Exception as e:
        return jsonify({'message': str(e)}), 500

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
        cursor.execute("UPDATE users SET name = ?, roll_number = ? WHERE email = ?", (name, roll_number, session['user']['email']))
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
    cursor.execute("INSERT INTO presets (academic_year, course, year, division, semester) VALUES (?, ?, ?, ?, ?)",
                   (academic_year, course, year, division, semester))
    conn.commit()
    conn.close()

    flash('Preset added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/presets/edit/<int:preset_id>', methods=['GET', 'POST'])
def edit_preset(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        academic_year = request.form['academic_year']
        course = request.form['course']
        year = request.form['year']
        division = request.form['division']
        semester = request.form['semester']
        
        cursor.execute("UPDATE presets SET academic_year = ?, course = ?, year = ?, division = ?, semester = ? WHERE id = ?",
                       (academic_year, course, year, division, semester, preset_id))
        conn.commit()
        conn.close()
        flash('Preset updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
    preset = cursor.fetchone()
    conn.close()
    return render_template('edit_preset.html', preset=preset)

@app.route('/admin/presets/delete/<int:preset_id>')
def delete_preset(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
    conn.commit()
    conn.close()
    flash('Preset deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/presets/<int:preset_id>/subjects')
def manage_subjects(preset_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM presets WHERE id = ?", (preset_id,))
    preset = cursor.fetchone()

    cursor.execute("SELECT * FROM subjects WHERE preset_id = ?", (preset_id,))
    subjects = cursor.fetchall()
    
    subject_components = {}
    for subject in subjects:
        cursor.execute("SELECT * FROM components WHERE subject_id = ?", (subject[0],))
        components = cursor.fetchall()
        subject_components[subject[0]] = components

    conn.close()
    
    return render_template('manage_subjects.html', preset=preset, subjects=subjects, subject_components=subject_components)

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
    cursor.execute("INSERT INTO subjects (preset_id, name, code, credits) VALUES (?, ?, ?, ?)",
                   (preset_id, name, code, credits))
    subject_id = cursor.lastrowid

    for component_name in components:
        max_marks = request.form.get(f'max_marks_{component_name}')
        if max_marks:
            cursor.execute("INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)",
                           (subject_id, component_name, max_marks))

    conn.commit()
    conn.close()
    flash('Subject added successfully!', 'success')
    return redirect(url_for('manage_subjects', preset_id=preset_id))

@app.route('/admin/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        credits = request.form['credits']
        
        cursor.execute("UPDATE subjects SET name = ?, code = ?, credits = ? WHERE id = ?",
                       (name, code, credits, subject_id))

        # Delete old components and add new ones
        cursor.execute("DELETE FROM components WHERE subject_id = ?", (subject_id,))
        components = request.form.getlist('components')
        for component_name in components:
            max_marks = request.form.get(f'max_marks_{component_name}')
            if max_marks:
                cursor.execute("INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)",
                               (subject_id, component_name, max_marks))

        conn.commit()
        
        cursor.execute("SELECT preset_id FROM subjects WHERE id = ?", (subject_id,))
        preset_id = cursor.fetchone()[0]
        conn.close()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('manage_subjects', preset_id=preset_id))

    cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    subject = cursor.fetchone()
    cursor.execute("SELECT * FROM components WHERE subject_id = ?", (subject_id,))
    components = cursor.fetchall()
    conn.close()
    
    return render_template('edit_subject.html', subject=subject, components=components)

@app.route('/admin/subjects/delete/<int:subject_id>')
def delete_subject(subject_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT preset_id FROM subjects WHERE id = ?", (subject_id,))
    preset_id = cursor.fetchone()[0]
    cursor.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    cursor.execute("DELETE FROM components WHERE subject_id = ?", (subject_id,))
    conn.commit()
    conn.close()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('manage_subjects', preset_id=preset_id))


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
        cursor.execute("SELECT id FROM presets WHERE academic_year = ? AND course = ? AND year = ? AND division = ? AND semester = ?",
                       (academic_year, course, year, division, semester))
        preset = cursor.fetchone()

        if action == 'load_subjects':
            if preset:
                preset_id = preset[0]
                cursor.execute("SELECT * FROM subjects WHERE preset_id = ?", (preset_id,))
                subjects = cursor.fetchall()
                
                subject_components = {}
                for subject in subjects:
                    cursor.execute("SELECT * FROM components WHERE subject_id = ?", (subject[0],))
                    components = cursor.fetchall()
                    subject_components[subject[0]] = components
                conn.close()
                return render_template('student.html', subjects=subjects, subject_components=subject_components,
                                       academic_year=academic_year, course=course, year=year, division=division, semester=semester)
            else:
                conn.close()
                return render_template('student.html', preset_not_found=True)
        
        elif action == 'calculate_cgpa':
            user_info = session['user']
            cursor.execute("SELECT id FROM users WHERE email = ?", (user_info['email'],))
            user_id = cursor.fetchone()[0]
            
            subject_ids = request.form.getlist('subjects')
            total_credits = 0
            total_grade_points = 0
            
            for subject_id in subject_ids:
                cursor.execute("SELECT credits FROM subjects WHERE id = ?", (subject_id,))
                credits = cursor.fetchone()[0]
                total_credits += credits

                cursor.execute("SELECT id, max_marks FROM components WHERE subject_id = ?", (subject_id,))
                components = cursor.fetchall()
                
                total_obtained_marks = 0
                total_max_marks = 0

                for component_id, max_marks in components:
                    marks_obtained = int(request.form[f'marks_{component_id}'])
                    total_obtained_marks += marks_obtained
                    total_max_marks += max_marks
                    
                    # Check if marks already exist
                    cursor.execute("SELECT id FROM student_marks WHERE user_id = ? AND component_id = ?", (user_id, component_id))
                    existing_mark = cursor.fetchone()
                    if existing_mark:
                        cursor.execute("UPDATE student_marks SET marks_obtained = ? WHERE id = ?", (marks_obtained, existing_mark[0]))
                    else:
                        cursor.execute("INSERT INTO student_marks (user_id, component_id, marks_obtained) VALUES (?, ?, ?)",
                                   (user_id, component_id, marks_obtained))

                percentage = (total_obtained_marks / total_max_marks) * 100
                
                cursor.execute("SELECT grade, grade_point FROM grading_rules WHERE ? BETWEEN min_percentage AND max_percentage", (percentage,))
                grade_info = cursor.fetchone()
                grade = grade_info[0]
                grade_point = grade_info[1]
                
                total_grade_points += grade_point * credits
                
                # Check if subject result already exists
                cursor.execute("SELECT id FROM subject_results WHERE user_id = ? AND subject_id = ?", (user_id, subject_id))
                existing_result = cursor.fetchone()
                if existing_result:
                    cursor.execute("UPDATE subject_results SET total_obtained = ?, total_max = ?, percentage = ?, grade = ?, grade_point = ? WHERE id = ?",
                                   (total_obtained_marks, total_max_marks, percentage, grade, grade_point, existing_result[0]))
                else:
                    cursor.execute("INSERT INTO subject_results (user_id, subject_id, total_obtained, total_max, percentage, grade, grade_point) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point))
            
            cgpa = total_grade_points / total_credits if total_credits > 0 else 0
            
            # Check if cgpa already exists
            cursor.execute("SELECT id FROM cgpa WHERE user_id = ?", (user_id,))
            existing_cgpa = cursor.fetchone()
            if existing_cgpa:
                cursor.execute("UPDATE cgpa SET cgpa = ? WHERE id = ?", (cgpa, existing_cgpa[0]))
            else:
                cursor.execute("INSERT INTO cgpa (user_id, cgpa) VALUES (?, ?)", (user_id, cgpa))
                
            conn.commit()
            conn.close()
            
            return redirect(url_for('view_result'))

    return render_template('student.html')

@app.route('/result')
def view_result():
    if 'user' not in session:
        return redirect(url_for('index'))

    user_info = session['user']
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (user_info['email'],))
    user_id = cursor.fetchone()[0]

    cursor.execute("SELECT s.name, sr.total_obtained, sr.total_max, sr.percentage, sr.grade, sr.grade_point FROM subject_results sr JOIN subjects s ON sr.subject_id = s.id WHERE sr.user_id = ?", (user_id,))
    subject_results = cursor.fetchall()

    cursor.execute("SELECT cgpa FROM cgpa WHERE user_id = ?", (user_id,))
    cgpa = cursor.fetchone()
    
    conn.close()

    return render_template('result.html', subject_results=subject_results, cgpa=cgpa)

@app.route('/download_pdf')
def download_pdf():
    if 'user' not in session:
        return redirect(url_for('index'))
    # PDF generation logic will be added here later
    flash('PDF download functionality is not yet implemented.', 'info')
    return redirect(url_for('view_result'))

@app.route('/admin/students')
def view_students():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_number, email FROM users WHERE is_admin = 0")
    students = cursor.fetchall()
    conn.close()

    return render_template('view_students.html', students=students)

@app.route('/admin/students/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_student_record(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))
    
    conn = create_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']
        
        cursor.execute("UPDATE users SET name = ?, roll_number = ? WHERE id = ?", (name, roll_number, user_id))
        conn.commit()
        conn.close()
        flash('Student record updated successfully!', 'success')
        return redirect(url_for('view_students'))

    cursor.execute("SELECT name, roll_number FROM users WHERE id = ?", (user_id,))
    student = cursor.fetchone()
    conn.close()
    
    return render_template('edit_student_record.html', student=student, user_id=user_id)

@app.route('/admin/students/delete/<int:user_id>')
def delete_student_record(user_id):
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    cursor.execute("DELETE FROM student_marks WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM subject_results WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM cgpa WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('Student record deleted successfully!', 'success')
    return redirect(url_for('view_students'))

@app.route('/admin/grading_rules', methods=['GET', 'POST'])
def manage_grading_rules():
    if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        rule_ids = request.form.getlist('rule_id')
        min_percentages = request.form.getlist('min_percentage')
        max_percentages = request.form.getlist('max_percentage')
        grades = request.form.getlist('grade')
        grade_points = request.form.getlist('grade_point')

        for i in range(len(rule_ids)):
            cursor.execute("UPDATE grading_rules SET min_percentage = ?, max_percentage = ?, grade = ?, grade_point = ? WHERE id = ?",
                           (min_percentages[i], max_percentages[i], grades[i], grade_points[i], rule_ids[i]))
        
        conn.commit()
        conn.close()
        flash('Grading rules updated successfully!', 'success')
        return redirect(url_for('manage_grading_rules'))

    cursor.execute("SELECT * FROM grading_rules")
    rules = cursor.fetchall()
    conn.close()

    return render_template('manage_grading_rules.html', rules=rules)


if __name__ == '__main__':
    app.run(debug=True)