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
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

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




@app.route('/')
def index():
    if 'user' in session:
        user_info = session['user']
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (user_info['email'],))
        user = cursor.fetchone()
        conn.close()

        admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
        if user_info['email'] in admin_emails:
            return redirect(url_for('admin_dashboard'))

        # Check if user exists and has all required fields (Name, Roll, Enrollment, Dept, Academic Year, Current Year)
        # Indexes: 2:name, 3:roll, 4:email (skip), 5:dept, 6:ac_year, 7:current_year
        if user and user[2] and user[3] and user[4] and user[5] and user[6] and user[7]:
             return redirect(url_for('student_dashboard'))
        else:
             return redirect(url_for('additional_info'))

    return render_template('login.html') 


# ... (skipping context)





@app.context_processor
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow(), 'dev_mode': DEV_MODE}

@app.route('/login')
def login():
    return google.authorize_redirect(url_for('authorize', _external=True))

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = google.get(google.server_metadata.get('userinfo_endpoint')).json()
        
        # Strict Domain Check
        email = user_info['email']
        if not email.endswith('@tsecmumbai.in') and email != ADMIN_EMAIL:
            # Revoke/Clear session immediately
            session.pop('user', None)
            return render_template('unauthorized.html')

        session['user'] = user_info

        conn = create_connection()
        cursor = conn.cursor()
        email = user_info['email']

        # Admin Logic from ENV (List supported)
        admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
        is_admin_email = email in admin_emails

        # Strict Domain Check for Students
        if not is_admin_email and not email.endswith('@tsecmumbai.in'):
             # Redirect to unauthorized page or show error
             return f"<h1>Access Denied</h1><p>Only @tsecmumbai.in emails are allowed. <a href='{url_for('login')}'>Go Back</a></p>", 403

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            is_admin = 1 if is_admin_email else 0
            cursor.execute(
                "INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)",
                (user_info['email'], user_info.get('name', 'Unknown'), is_admin)
            )
            conn.commit()
        else:
            # Update Admin Status if changed
            current_is_admin = user[8] # Ensure index is correct based on schema
            expected_is_admin = 1 if is_admin_email else 0
            
            if current_is_admin != expected_is_admin:
                cursor.execute(
                    "UPDATE users SET is_admin = ? WHERE email = ?",
                    (expected_is_admin, email)
                )
                conn.commit()

        # Name Consistency: Update session with DB name (in case user edited it locally)
        # Re-fetch name from DB to be sure
        cursor.execute("SELECT name FROM users WHERE email=?", (user_info['email'],))
        db_name = cursor.fetchone()[0]
        if db_name:
            session['user']['name'] = db_name
            session.modified = True

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
        enrollment_number = request.form['enrollment_number']
        department = request.form['department']
        academic_year = request.form['academic_year']
        current_year = request.form['current_year']

        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users 
            SET name = ?, roll_number = ?, enrollment_number = ?, department = ?, academic_year = ?, current_year = ?
            WHERE email = ?
            """,
            (name, roll_number, enrollment_number, department, academic_year, current_year, session['user']['email'])
        )
        conn.commit()
        conn.close()

        # Name Consistency: Update session immediately
        session['user']['name'] = name
        session.modified = True

        return redirect(url_for('student_dashboard'))



    return render_template('additional_info.html')

@app.route('/view_profile')
def view_profile():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, roll_number, enrollment_number, department, academic_year, current_year FROM users WHERE email=?", (session['user']['email'],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return redirect(url_for('logout'))

    return render_template('view_profile.html', user=user)


@app.route('/admin/db/download')
def download_db():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))
    
    try:
        return send_file('database.db', as_attachment=True)
    except Exception as e:
        flash(f"Error downloading database: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/db/upload', methods=['POST'])
def upload_db():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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


@app.route('/admin/db/migrate', methods=['POST'])
def migrate_db():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
            import os
            import sys
            
            # Save uploaded file temporarily
            temp_old_db = 'temp_old_backup.db'
            file.save(temp_old_db)
            
            # Import migration function
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'migration_tools'))
            from migrate_database import migrate_database
            
            # Run migration
            temp_migrated_db = 'temp_migrated.db'
            success = migrate_database(temp_old_db, temp_migrated_db)
            
            if success:
                # Backup current database
                import shutil
                from datetime import datetime
                backup_name = f'backup_before_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
                if os.path.exists('database.db'):
                    shutil.copy('database.db', backup_name)
                
                # Replace with migrated database
                shutil.move(temp_migrated_db, 'database.db')
                
                # Cleanup
                if os.path.exists(temp_old_db):
                    os.remove(temp_old_db)
                
                flash(f'Database migrated successfully! Old database backed up as {backup_name}', 'success')
            else:
                flash('Migration failed. Please check the uploaded file.', 'error')
                
        except Exception as e:
            flash(f"Error during migration: {str(e)}", "error")
            import traceback
            print(traceback.format_exc())
        finally:
            # Cleanup temp files
            if os.path.exists('temp_old_backup.db'):
                os.remove('temp_old_backup.db')
            if os.path.exists('temp_migrated.db'):
                os.remove('temp_migrated.db')
            
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/presets/delete/<int:preset_id>')
def delete_preset(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    # Cascade delete (Subjects -> Components) handled? No, SQLite FK default is NO ACTION often unless ON DELETE CASCADE set.
    # Manual cleanup is safer.
    cursor.execute("SELECT id FROM subjects WHERE preset_id=?", (preset_id,))
    subjects = cursor.fetchall()
    
    for subj in subjects:
        cursor.execute("DELETE FROM components WHERE subject_id=?", (subj[0],))
    
    cursor.execute("DELETE FROM subjects WHERE preset_id=?", (preset_id,))
    cursor.execute("DELETE FROM presets WHERE id=?", (preset_id,))

    conn.commit()
    conn.close()

    flash("Preset deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/presets/edit/<int:preset_id>', methods=['POST'])
def edit_preset(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    academic_year = request.form['academic_year']
    course = request.form['course']
    department = request.form['department'] # New Field
    year = request.form['year']
    division = request.form['division']
    semester = request.form['semester']

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE presets SET academic_year=?, course=?, department=?, year=?, division=?, semester=? WHERE id=?",
        (academic_year, course, department, year, division, semester, preset_id)
    )
    conn.commit()
    conn.close()

    flash('Preset updated successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/presets/duplicate/<int:preset_id>', methods=['POST'])
def duplicate_preset(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    # 1. Create the NEW Preset
    academic_year = request.form['academic_year']
    course = request.form['course']
    department = request.form['department'] # New Field
    year = request.form['year']
    division = request.form['division']
    semester = request.form['semester']

    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO presets (academic_year, course, department, year, division, semester) VALUES (?, ?, ?, ?, ?, ?)",
        (academic_year, course, department, year, division, semester)
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
    # Admin Logic from ENV (List supported)
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM presets")
    presets = cursor.fetchall()
    conn.close()
    return render_template('admin.html', presets=presets)
@app.route('/admin/presets/add', methods=['POST'])
def add_preset():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    academic_year = request.form['academic_year']
    department = request.form['department'] # New Field
    course = 'BE' # Hardcoded
    year = request.form['year']
    division = request.form['division']
    semester = request.form['semester']

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO presets (academic_year, course, department, year, division, semester) VALUES (?, ?, ?, ?, ?, ?)",
        (academic_year, course, department, year, division, semester)
    )
    conn.commit()
    conn.close()

    flash('Preset added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/student', methods=['GET', 'POST'])
def student_dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = create_connection()
    cursor = conn.cursor()

    user_email = session['user']['email']
    user_email = session['user']['email']
    # Fetch user details including department and current_year
    cursor.execute("SELECT id, name, roll_number, current_year, department FROM users WHERE email=?", (user_email,))
    user = cursor.fetchone()
    
    if not user:
         conn.close()
         session.pop('user', None)
         return redirect(url_for('login'))

    user_id = user[0]
    current_year = user[3]
    department = user[4]

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'load_subjects':
            preset_id = request.form.get('preset_id')
            
            if not preset_id:
                flash("Please select a class.", "error")
                return redirect(url_for('student_dashboard'))
                
            cursor.execute("SELECT * FROM presets WHERE id=?", (preset_id,))
            preset = cursor.fetchone()

            if not preset:
                flash("Selected class not found.", "error")
                return redirect(url_for('student_dashboard'))

            cursor.execute("SELECT * FROM subjects WHERE preset_id=?", (preset_id,))
            subjects = cursor.fetchall()

            subject_components = {}
            for s in subjects:
                cursor.execute("SELECT * FROM components WHERE subject_id=?", (s[0],))
                subject_components[s[0]] = cursor.fetchall()
            
            # Fetch existing marks for this user and preset
            # We want to map component_id -> marks_obtained
            marks_map = {}
            cursor.execute("""
                SELECT component_id, marks_obtained FROM student_marks 
                WHERE user_id=? AND component_id IN (
                    SELECT id FROM components WHERE subject_id IN (
                        SELECT id FROM subjects WHERE preset_id=?
                    )
                )
            """, (user_id, preset_id))
            existing_marks = cursor.fetchall()
            for m in existing_marks:
                marks_map[m[0]] = m[1]
            
            # Fetch presets (Filtered by current_year)
            # Fetch presets (Filtered by current_year and department)
            if current_year and department:
                 # Check if department column exists is handled by schema update
                cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE year=? AND department=?", (current_year, department))
            elif current_year:
                cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE year=?", (current_year,))
            else:
                cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets")
            presets = cursor.fetchall()
            
            conn.close()
            return render_template(
                'student.html',
                presets=presets,
                selected_preset=preset,
                subjects=subjects,
                subject_components=subject_components,
                marks_map=marks_map, # Pass marks to template
                user=user
            )

        elif action == 'calculate_cgpa':
            try:
                subject_ids = request.form.getlist('subjects')
                
                if not subject_ids:
                     flash("No subjects selected/found.", "error")
                     return redirect(url_for('student_dashboard'))

                total_credits = 0
                total_weighted_points = 0
                
                for subject_id in subject_ids:
                    cursor.execute("SELECT credits FROM subjects WHERE id=?", (subject_id,))
                    res_credits = cursor.fetchone()
                    if not res_credits: 
                        continue 
                    credits = res_credits[0]

                    cursor.execute("SELECT id, max_marks FROM components WHERE subject_id=?", (subject_id,))
                    components = cursor.fetchall()

                    total_obtained = 0
                    total_max = 0

                    for comp_id, max_marks in components:
                        marks_str = request.form.get(f'marks_{comp_id}', '0')
                        if not marks_str or not marks_str.strip():
                            marks_str = '0'
                        marks_str = marks_str.strip()
                        if not marks_str.replace('.', '', 1).isdigit():
                            marks_str = '0'
                        marks = float(marks_str)
                        
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
                        grade, grade_point = 'F', 0.0

                    total_credits += credits
                    total_weighted_points += grade_point * credits

                    cursor.execute(
                        "INSERT OR REPLACE INTO subject_results (user_id, subject_id, total_obtained_marks, total_max_marks, percentage, grade, grade_point) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (user_id, subject_id, total_obtained, total_max, percentage, grade, grade_point)
                    )

                cgpa = total_weighted_points / total_credits if total_credits else 0

                cursor.execute(
                    "INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)",
                    (user_id, cgpa)
                )

                conn.commit()
                conn.close()
                
                flash("Grades calculated successfully!", "success")
                return redirect(url_for('view_result'))
                
            except Exception as e:
                if 'conn' in locals():
                    conn.rollback()
                    conn.close()
                flash(f"An error occurred during calculation: {str(e)}", "error")
                return redirect(url_for('student_dashboard'))

    # GET request: Fetch presets filtered by user's current year and department
    if current_year and department:
        cursor.execute("SELECT id, academic_year, course, year, division, semester FROM presets WHERE year=? AND department=?", (current_year, department))
    elif current_year:
        cursor.execute("SELECT id, academic_year, course, year, division, semester FROM presets WHERE year=?", (current_year,))
    else:
        cursor.execute("SELECT id, academic_year, course, year, division, semester FROM presets")
    presets = cursor.fetchall()
    
    conn.close()
    return render_template('student.html', presets=presets, user=user)





@app.route('/result')
def view_result():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id FROM users WHERE email=?", (session['user']['email'],))
        user_res = cursor.fetchone()
        
        if not user_res:
            session.pop('user', None)
            flash("Session expired or user not found. Please log in again.", "error")
            return redirect(url_for('login'))
            
        user_id = user_res[0]

        # Fetch subject results joined with subject and preset info
        cursor.execute("""
            SELECT 
                p.id as preset_id,
                p.course,
                p.year,
                p.semester,
                s.name as subject_name, 
                sr.total_obtained_marks, 
                sr.total_max_marks, 
                sr.percentage, 
                sr.grade, 
                sr.grade_point,
                s.credits
            FROM subject_results sr
            JOIN subjects s ON sr.subject_id = s.id
            JOIN presets p ON s.preset_id = p.id
            WHERE sr.user_id = ?
            ORDER BY p.year DESC, p.semester DESC
        """, (user_id,))
        
        raw_results = cursor.fetchall()
        
        # Group results by preset (Semester)
        grouped_results = {}
        # Structure: { preset_id: { 'details': preset_details, 'subjects': [], 'sgpa': 0.0 } }
        
        for row in raw_results:
            preset_id = row[0]
            if preset_id not in grouped_results:
                grouped_results[preset_id] = {
                    'course': row[1],
                    'year': row[2],
                    'semester': row[3],
                    'subjects': [],
                    'total_credits': 0,
                    'total_points': 0
                }
            
            # Add subject info
            grouped_results[preset_id]['subjects'].append({
                'name': row[4],
                'obtained': row[5],
                'max': row[6],
                'percentage': row[7],
                'grade': row[8],
                'point': row[9],
                'credits': row[10]
            })
            
            # Accumulate for SGPA
            grouped_results[preset_id]['total_credits'] += row[10]
            grouped_results[preset_id]['total_points'] += (row[9] * row[10]) # grade_point * credits

        # Calculate SGPA for each group
        for pid, data in grouped_results.items():
            if data['total_credits'] > 0:
                data['sgpa'] = round(data['total_points'] / data['total_credits'], 2)
            else:
                data['sgpa'] = 0.0

        conn.close()
        return render_template('result.html', grouped_results=grouped_results)
        
    except Exception as e:
        import traceback
        print(f"Error viewing results: {e}")
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.close()
        flash("An error occurred while loading results.", "error")
        return redirect(url_for('student_dashboard'))


@app.route('/admin/students')
def view_students():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_number, email, enrollment_number, department, academic_year, current_year FROM users WHERE is_admin=0")
    students = cursor.fetchall()
    conn.close()

    return render_template('view_students.html', students=students)


@app.route('/admin/grading_rules', methods=['GET', 'POST'])
def manage_grading_rules():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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


@app.route('/admin/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
def edit_subject(subject_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        code = request.form['code']
        credits = request.form['credits']
        
        cursor.execute("UPDATE subjects SET name=?, code=?, credits=? WHERE id=?", (name, code, credits, subject_id))
        conn.commit()
        conn.close()
        
        # Determine redirect target (preset_id is needed for manage_subjects)
        preset_id = request.args.get('preset_id')
        if preset_id:
             return redirect(url_for('manage_subjects', preset_id=preset_id))
        else:
             # Fallback if preset_id lost, though usually passed in query string
             return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
    subject = cursor.fetchone()
    conn.close()
    
    if not subject:
         flash('Subject not found', 'error')
         return redirect(url_for('admin_dashboard'))

    return render_template('edit_subject.html', subject=subject)

@app.route('/admin/subjects/<int:preset_id>', methods=['GET'])
def manage_subjects(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']

        department = request.form['department']
        enrollment_number = request.form['enrollment_number']
        academic_year = request.form['academic_year']
        current_year = request.form['current_year']

        cursor.execute(
            "UPDATE users SET name=?, roll_number=?, enrollment_number=?, department=?, academic_year=?, current_year=? WHERE id=?",
            (name, roll_number, enrollment_number, department, academic_year, current_year, user_id)
        )

        conn.commit()
        conn.close()

        flash("Student updated!", "success")
        return redirect(url_for('view_students'))

    cursor.execute("SELECT name, roll_number, enrollment_number, department, academic_year, current_year FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()

    conn.close()
    return render_template('edit_student_record.html', student=student, user_id=user_id)


@app.route('/admin/students/delete/<int:user_id>')
def delete_student_record(user_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()

    # Fetch subject results joined with subject and preset info
    cursor.execute("""
        SELECT 
            p.id as preset_id,
            p.course,
            p.year,
            p.semester,
            s.name as subject_name, 
            s.code,
            s.credits,
            sr.total_obtained_marks, 
            sr.total_max_marks, 
            sr.percentage, 
            sr.grade, 
            sr.grade_point,
            s.id as subject_id
        FROM subject_results sr
        JOIN subjects s ON sr.subject_id = s.id
        JOIN presets p ON s.preset_id = p.id
        WHERE sr.user_id = ?
        ORDER BY p.year DESC, p.semester DESC
    """, (user_id,))
    
    raw_results = cursor.fetchall()
    
    grouped_results = {}
    detailed_marks = {}

    for row in raw_results:
        preset_id = row[0]
        subject_id = row[12]
        
        if preset_id not in grouped_results:
            grouped_results[preset_id] = {
                'course': row[1],
                'year': row[2],
                'semester': row[3],
                'subjects': [],
                'total_credits': 0,
                'total_points': 0
            }
        
        grouped_results[preset_id]['subjects'].append({
            'name': row[4],
            'code': row[5],
            'credits': row[6],
            'obtained': row[7],
            'max': row[8],
            'percentage': row[9],
            'grade': row[10],
            'point': row[11],
            'id': subject_id
        })
        
        grouped_results[preset_id]['total_credits'] += row[6]
        grouped_results[preset_id]['total_points'] += (row[11] * row[6])

        # Fetch component marks for this subject
        cursor.execute("""
            SELECT c.name, sm.marks_obtained, c.max_marks
            FROM student_marks sm
            JOIN components c ON sm.component_id = c.id
            WHERE sm.user_id = ? AND c.subject_id = ?
        """, (user_id, subject_id))
        detailed_marks[subject_id] = cursor.fetchall()

    # Calculate SGPA for each group
    for pid, data in grouped_results.items():
        if data['total_credits'] > 0:
            data['sgpa'] = round(data['total_points'] / data['total_credits'], 2)
        else:
            data['sgpa'] = 0.0

    # Get Final CGPA
    cursor.execute("SELECT cgpa FROM cgpa WHERE user_id=?", (user_id,))
    cgpa_data = cursor.fetchone()
    cgpa = cgpa_data[0] if cgpa_data else 0

    conn.close()

    return render_template(
        'admin_student_results.html',
        student=student,
        grouped_results=grouped_results,
        detailed_marks=detailed_marks,
        cgpa=cgpa
    )


@app.route('/admin/students/<int:user_id>/download_csv')
def download_student_csv(user_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    import csv
    import io

    conn = create_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT name, roll_number, email, enrollment_number, department, current_year FROM users WHERE id=?", (user_id,))
    student = cursor.fetchone()
    student_name = student[0]

    # Get Marks Data
    # ... (skipping context)

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Student Report'])
    writer.writerow(['Name', student[0]])
    writer.writerow(['Roll Number', student[1]])
    writer.writerow(['Email', student[2]])
    writer.writerow(['Enrollment Number', student[3] or '-'])
    writer.writerow(['Department', student[4] or '-'])
    writer.writerow(['Current Year', student[5] or '-'])
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
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


@app.route('/dev_login', methods=['GET', 'POST'])
def dev_login():
    if not DEV_MODE:
        return "Developer Mode Not Enabled", 403

    if request.method == 'POST':
        role = request.form.get('role', 'student')
        
        if role == 'admin':
            admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
            email = admin_emails[0] if admin_emails else "admin@tsecmumbai.in"
            # User wants "developer mode". Let's use the real admin email so they can access admin dashboard 
            # if the real admin email is hardcoded.
            # But wait, logic at line 122 of original file checks user_info['email'] == ADMIN_EMAIL.
            pass
        
        email = "dev.admin@tsecmumbai.in" if role == 'admin' else "dev.student@tsecmumbai.in"
        # Wait, if I use dev.admin, I must ensure it is granted is_admin=1 in DB.
        
        name = "Dev Admin" if role == 'admin' else "Dev Student"
        
        # Override for testing actual admin logic if needed
        if role == 'admin':
             # Check if we should use the hardcoded admin email to pass strict checks?
             # existing code checks `if user_info['email'] == ADMIN_EMAIL`.
             # So I MUST use `ADMIN_EMAIL` to be recognized as Admin in `admin_dashboard`?
             # Line 365: `if 'user' not in session or session['user']['email'] != ADMIN_EMAIL:`
             # Yes. I must use the specific email.
             admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
             email = admin_emails[0] if admin_emails else "admin@tsecmumbai.in"
             name = "Dev Admin (Master)"

        user_info = {
            'email': email,
            'name': name,
            'picture': 'https://ui-avatars.com/api/?name=' + name.replace(' ', '+')
        }
        
        conn = create_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        u = c.fetchone()
        
        if not u:
             c.execute("INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)", 
                       (email, name, 1 if role=='admin' else 0))
             conn.commit()
        else:
             # Ensure admin status match
             current_status = u[8] # is_admin
             target_status = 1 if role == 'admin' else 0
             if current_status != target_status:
                 c.execute("UPDATE users SET is_admin=? WHERE email=?", (target_status, email))
                 conn.commit()
             
             # Sync name if existing user
             user_info['name'] = u[2]

        conn.close()
        
        session['user'] = user_info
        return redirect('/')
        
    return render_template('dev_login.html')

@app.route('/admin/promote', methods=['GET', 'POST'])
def promote_students():
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        from_year = request.form['from_year']
        to_year = request.form['to_year']
        
        conn = create_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE current_year=?", (from_year,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            cursor.execute("UPDATE users SET current_year=? WHERE current_year=?", (to_year, from_year))
            conn.commit()
            flash(f"Successfully promoted {count} students from {from_year} to {to_year}!", "success")
        else:
            flash(f"No students found in {from_year}.", "warning")
            
        conn.close()
        return redirect(url_for('promote_students'))
        
    return render_template('promote_students.html')

if __name__ == '__main__':
    create_tables()
    app.run(debug=True)