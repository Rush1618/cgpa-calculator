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
def inject_now():
    admin_emails = [e.strip() for e in os.getenv('ADMIN_EMAILS', '').split(',') if e.strip()]
    return {
        'now': datetime.utcnow(), 
        'dev_mode': DEV_MODE,
        'admin_emails': admin_emails
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if DEV_MODE and request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name', 'Dev User')
        
        if not email:
            flash("Email is required", "error")
            return redirect(url_for('login'))

        user_info = {
            'email': email,
            'name': name,
            'picture': 'https://ui-avatars.com/api/?name=' + name.replace(' ', '+')
        }
        session['user'] = user_info

        conn = create_connection()
        cursor = conn.cursor()
        
        # Admin check
        admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
        is_admin = 1 if email in admin_emails else 0

        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if not user:
            cursor.execute(
                "INSERT INTO users (email, name, is_admin) VALUES (?, ?, ?)",
                (email, name, is_admin)
            )
            conn.commit()
        else:
            # Sync admin status
            if user[8] != is_admin:
                cursor.execute("UPDATE users SET is_admin = ? WHERE email = ?", (is_admin, email))
                conn.commit()
            
            # Sync name
            session['user']['name'] = user[2]
            session.modified = True

        conn.close()
        return redirect(url_for('index'))

    if DEV_MODE:
        return render_template('login.html', dev_mode=True)
    
    return redirect(url_for('google_login'))

@app.route('/login/google')
def google_login():
    return google.authorize_redirect(url_for('authorize', _external=True))

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        user_info = google.get(google.server_metadata.get('userinfo_endpoint')).json()
        
        # Strict Domain Check
        email = user_info['email']
        # Load admin emails for bypass check
        admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
        
        if not email.endswith('@tsecmumbai.in') and email not in admin_emails:
            # Revoke/Clear session immediately
            session.pop('user', None)
            return render_template('unauthorized.html')

        session['user'] = user_info

        conn = create_connection()
        cursor = conn.cursor()
        # Admin Logic from ENV (List supported)
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

    ENROLL_PREFIX = 'MU034112024020'

    if request.method == 'POST':
        name = request.form['name']
        roll_number = request.form['roll_number']
        enrollment_raw = request.form.get('enrollment_number', '').strip()
        department = request.form['department']
        academic_year = request.form['academic_year']
        current_year = request.form['current_year']

        # Server-side safety: ensure prefix is always present
        if not enrollment_raw.startswith(ENROLL_PREFIX):
            # If user somehow bypassed JS, treat whatever they typed as the suffix
            enrollment_number = ENROLL_PREFIX + enrollment_raw
        else:
            enrollment_number = enrollment_raw

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


@app.route('/admin/presets/<int:preset_id>/results')
def view_preset_results(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE id = ?", (preset_id,))
    preset = cursor.fetchone()
    if not preset:
        conn.close()
        flash("Preset not found", "error")
        return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT id, name, code, credits FROM subjects WHERE preset_id = ?", (preset_id,))
    subjects = cursor.fetchall()
    total_credits = sum(sub[3] for sub in subjects) if subjects else 0

    students_data = []
    total_students = 0
    pass_count = 0
    fail_count = 0
    avg_sgpa = 0.0

    if subjects:
        subject_ids = [s[0] for s in subjects]
        placeholders = ','.join(['?'] * len(subject_ids))
        cursor.execute(f"""
            SELECT DISTINCT u.id, u.name, u.roll_number 
            FROM users u
            JOIN subject_results sr ON u.id = sr.user_id
            WHERE sr.subject_id IN ({placeholders})
            ORDER BY u.roll_number
        """, subject_ids)
        students = cursor.fetchall()
        total_students = len(students)
        
        total_sgpa_sum = 0.0
        
        for student in students:
            user_id, student_name, roll_number = student
            
            cursor.execute(f"""
                SELECT sr.subject_id, sr.total_obtained_marks, sr.total_max_marks, sr.percentage, sr.grade, sr.grade_point, s.credits
                FROM subject_results sr
                JOIN subjects s ON sr.subject_id = s.id
                WHERE sr.user_id = ? AND sr.subject_id IN ({placeholders})
            """, [user_id] + subject_ids)
            marks_rows = cursor.fetchall()
            
            marks_map = {}
            total_credits = 0.0
            total_points = 0.0
            has_fail = False
            
            for m_row in marks_rows:
                sub_id, obtained, max_m, percentage, grade, grade_point, credits = m_row
                marks_map[sub_id] = {
                    'grade': grade,
                    'percentage': percentage,
                    'obtained': obtained,
                    'max': max_m
                }
                total_credits += credits
                total_points += grade_point * credits
                if grade == 'F':
                    has_fail = True
            
            sgpa = total_points / total_credits if total_credits > 0 else 0.0
            total_sgpa_sum += sgpa
            
            if has_fail:
                fail_count += 1
            else:
                pass_count += 1
                
            students_data.append({
                'user_id': user_id,
                'name': student_name,
                'roll': roll_number,
                'marks': marks_map,
                'sgpa': sgpa,
                'has_fail': has_fail
            })
            
        if total_students > 0:
            avg_sgpa = total_sgpa_sum / total_students

    conn.close()
    return render_template(
        'preset_results.html',
        preset=preset,
        subjects=subjects,
        students_data=students_data,
        total_students=total_students,
        pass_count=pass_count,
        fail_count=fail_count,
        avg_sgpa=avg_sgpa,
        total_credits=total_credits
    )


@app.route('/admin/presets/<int:preset_id>/results/csv')
def download_preset_results_csv(preset_id):
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' not in session or session['user']['email'] not in admin_emails:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE id = ?", (preset_id,))
    preset = cursor.fetchone()
    if not preset:
        conn.close()
        flash("Preset not found", "error")
        return redirect(url_for('admin_dashboard'))
        
    cursor.execute("SELECT id, name, code, credits FROM subjects WHERE preset_id = ?", (preset_id,))
    subjects = cursor.fetchall()
    
    import csv
    import io
    from flask import make_response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = ['Roll Number', 'Name'] + [f"{sub[1]} (Grade)" for sub in subjects] + ['SGPA', 'Status']
    writer.writerow(headers)
    
    if subjects:
        subject_ids = [s[0] for s in subjects]
        placeholders = ','.join(['?'] * len(subject_ids))
        cursor.execute(f"""
            SELECT DISTINCT u.id, u.name, u.roll_number 
            FROM users u
            JOIN subject_results sr ON u.id = sr.user_id
            WHERE sr.subject_id IN ({placeholders})
            ORDER BY u.roll_number
        """, subject_ids)
        students = cursor.fetchall()
        
        for student in students:
            user_id, student_name, roll_number = student
            
            cursor.execute(f"""
                SELECT sr.subject_id, sr.percentage, sr.grade, sr.grade_point, s.credits
                FROM subject_results sr
                JOIN subjects s ON sr.subject_id = s.id
                WHERE sr.user_id = ? AND sr.subject_id IN ({placeholders})
            """, [user_id] + subject_ids)
            marks_rows = cursor.fetchall()
            
            marks_map = {}
            total_credits = 0.0
            total_points = 0.0
            has_fail = False
            
            for m_row in marks_rows:
                sub_id, percentage, grade, grade_point, credits = m_row
                marks_map[sub_id] = grade
                total_credits += credits
                total_points += grade_point * credits
                if grade == 'F':
                    has_fail = True
                    
            sgpa = total_points / total_credits if total_credits > 0 else 0.0
            status = 'FAIL' if has_fail else 'PASS'
            
            row_data = [roll_number, student_name]
            for sub in subjects:
                grade = marks_map.get(sub[0], '-')
                row_data.append(grade)
            row_data.append(f"{sgpa:.2f}")
            row_data.append(status)
            
            writer.writerow(row_data)
            
    conn.close()
    
    preset_name = f"{preset[3] or 'General'}_{preset[4]}Yr_Sem{preset[6]}".replace(" ", "_")
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=ClassResults_{preset_name}.csv"
    response.headers["Content-type"] = "text/csv"
    return response


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

                    # Find new grade from rules
                    cursor.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
                    rules = cursor.fetchall()
                    
                    grade, grade_point = 'F', 0.0
                    for min_p, max_p, g, p in rules:
                        if percentage >= min_p and percentage <= max_p:
                            grade, grade_point = g, p
                            break

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
        cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE year=? AND department=?", (current_year, department))
    elif current_year:
        cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets WHERE year=?", (current_year,))
    else:
        cursor.execute("SELECT id, academic_year, course, department, year, division, semester FROM presets")
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
        cursor.execute("SELECT id, current_year FROM users WHERE email=?", (session['user']['email'],))
        user_res = cursor.fetchone()
        
        if not user_res:
            session.pop('user', None)
            flash("Session expired or user not found. Please log in again.", "error")
            return redirect(url_for('login'))
            
        user_id = user_res[0]
        student_current_semester = user_res[1] or "N/A"

        # Fetch ALL subject results across ALL semesters, joined with subject and preset info
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
                s.credits,
                s.code,
                s.id as subject_id
            FROM subject_results sr
            JOIN subjects s ON sr.subject_id = s.id
            JOIN presets p ON s.preset_id = p.id
            WHERE sr.user_id = ?
            ORDER BY p.year ASC, p.semester ASC
        """, (user_id,))
        
        raw_results = cursor.fetchall()
        
        # Group results by preset (one preset = one semester block)
        grouped_results = {}
        
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
            
            grouped_results[preset_id]['subjects'].append({
                'id': row[12],
                'name': row[4],
                'code': row[11] or '',
                'obtained': row[5],
                'max': row[6],
                'percentage': row[7],
                'grade': row[8],
                'point': row[9],
                'credits': row[10]
            })
            
            grouped_results[preset_id]['total_credits'] += row[10]
            grouped_results[preset_id]['total_points'] += (row[9] * row[10])

        # Calculate SGPA per semester + accumulate for overall CGPA
        all_credits = 0
        all_points = 0
        for pid, data in grouped_results.items():
            if data['total_credits'] > 0:
                data['sgpa'] = round(data['total_points'] / data['total_credits'], 2)
            else:
                data['sgpa'] = 0.0
            all_credits += data['total_credits']
            all_points += data['total_points']

        # Overall CGPA = weighted average across all semesters
        overall_cgpa = round(all_points / all_credits, 2) if all_credits > 0 else 0.0

        conn.close()
        return render_template('result.html',
                               grouped_results=grouped_results,
                               overall_cgpa=overall_cgpa,
                               student_current_semester=student_current_semester)
        
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
            try:
                # Basic validation: ensure values aren't empty
                min_val = float(mins[i]) if mins[i] else 0.0
                max_val = float(maxs[i]) if maxs[i] else 100.0
                grade_val = grades[i].upper() if grades[i] else 'F'
                point_val = float(points[i]) if points[i] else 0.0
                
                cursor.execute(
                    "UPDATE grading_rules SET min_percentage=?, max_percentage=?, grade=?, grade_point=? WHERE id=?",
                    (min_val, max_val, grade_val, point_val, rule_ids[i])
                )
            except (ValueError, IndexError):
                continue

        # Recalculate all grades and CGPA since rules changed
        cursor.execute("SELECT min_percentage, max_percentage, grade, grade_point FROM grading_rules")
        current_rules = cursor.fetchall()

        cursor.execute("PRAGMA table_info(subject_results)")
        columns = [col[1] for col in cursor.fetchall()]
        obt_col = 'total_obtained_marks' if 'total_obtained_marks' in columns else 'total_obtained'
        max_col = 'total_max_marks' if 'total_max_marks' in columns else 'total_max'

        cursor.execute(f"SELECT id, user_id, {obt_col}, {max_col} FROM subject_results")
        all_results = cursor.fetchall()

        for res_id, u_id, obt, mx in all_results:
            perc = (obt / mx * 100) if mx and mx > 0 else 0
            new_g, new_p = 'F', 0.0
            for r_min, r_max, r_g, r_p in current_rules:
                if perc >= r_min and perc <= r_max:
                    new_g, new_p = r_g, r_p
                    break
            cursor.execute("UPDATE subject_results SET percentage=?, grade=?, grade_point=? WHERE id=?", (perc, new_g, new_p, res_id))

        # Update CGPAs
        cursor.execute("SELECT DISTINCT user_id FROM subject_results")
        u_ids = cursor.fetchall()
        for (u_id,) in u_ids:
            cursor.execute("SELECT sr.grade_point, s.credits FROM subject_results sr JOIN subjects s ON sr.subject_id = s.id WHERE sr.user_id=?", (u_id,))
            marks = cursor.fetchall()
            t_cred = sum(m[1] for m in marks)
            t_pts = sum(m[0] * m[1] for m in marks)
            new_cgpa = t_pts / t_cred if t_cred > 0 else 0
            cursor.execute("INSERT OR REPLACE INTO cgpa (user_id, cgpa) VALUES (?, ?)", (u_id, new_cgpa))

        conn.commit()
        flash("Grading rules updated and all student records recalculated!", "success")

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
        
        # Component management
        cursor.execute("SELECT name FROM components WHERE subject_id = ?", (subject_id,))
        existing_components = {row[0] for row in cursor.fetchall()}
        
        selected_components = request.form.getlist('components')
        
        # 1. Delete deselected components
        for comp_name in list(existing_components):
            if comp_name not in selected_components:
                cursor.execute("SELECT id FROM components WHERE subject_id = ? AND name = ?", (subject_id, comp_name))
                comp_res = cursor.fetchone()
                if comp_res:
                    cursor.execute("DELETE FROM student_marks WHERE component_id = ?", (comp_res[0],))
                cursor.execute("DELETE FROM components WHERE subject_id = ? AND name = ?", (subject_id, comp_name))
                
        # 2. Insert or update selected components
        for comp_name in selected_components:
            max_marks = request.form.get(f'max_marks_{comp_name}')
            if comp_name in existing_components:
                cursor.execute("UPDATE components SET max_marks = ? WHERE subject_id = ? AND name = ?", (max_marks, subject_id, comp_name))
            else:
                cursor.execute("INSERT INTO components (subject_id, name, max_marks) VALUES (?, ?, ?)", (subject_id, comp_name, max_marks))
        
        conn.commit()
        conn.close()
        
        preset_id = request.args.get('preset_id')
        if preset_id:
             return redirect(url_for('manage_subjects', preset_id=preset_id))
        else:
             return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM subjects WHERE id=?", (subject_id,))
    subject = cursor.fetchone()
    
    if not subject:
         conn.close()
         flash('Subject not found', 'error')
         return redirect(url_for('admin_dashboard'))
         
    cursor.execute("SELECT name, max_marks FROM components WHERE subject_id=?", (subject_id,))
    components_list = cursor.fetchall()
    components_map = {row[0]: row[1] for row in components_list}
    
    conn.close()
    
    preset_id = request.args.get('preset_id') or subject[1]
    return render_template('edit_subject.html', subject=subject, components_map=components_map, preset_id=preset_id)

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

    total_credits = sum(subj[4] for subj in subjects) if subjects else 0

    return render_template(
        'manage_subjects.html',
        preset=preset,
        subjects=subjects,
        subject_components=subject_components,
        total_credits=total_credits
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
        is_admin = int(request.form.get('is_admin', 0))

        cursor.execute(
            "UPDATE users SET name=?, roll_number=?, enrollment_number=?, department=?, academic_year=?, current_year=?, is_admin=? WHERE id=?",
            (name, roll_number, enrollment_number, department, academic_year, current_year, is_admin, user_id)
        )

        conn.commit()
        conn.close()

        flash("Student updated!", "success")
        return redirect(url_for('view_students'))

    cursor.execute("SELECT name, roll_number, enrollment_number, department, academic_year, current_year, is_admin FROM users WHERE id=?", (user_id,))
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
@app.route('/result/pdf')
def download_pdf():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = create_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, name, roll_number, enrollment_number, department, current_year FROM users WHERE email=?", (session['user']['email'],))
        user_res = cursor.fetchone()
        
        if not user_res:
            session.pop('user', None)
            flash("Session expired or user not found. Please log in again.", "error")
            return redirect(url_for('login'))
            
        user_id, student_name, roll_number, enrollment_number, department, current_year = user_res

        # Fetch results
        cursor.execute("""
            SELECT 
                p.course,
                p.year,
                p.semester,
                s.name as subject_name, 
                sr.total_obtained_marks, 
                sr.total_max_marks, 
                sr.percentage, 
                sr.grade, 
                sr.grade_point,
                s.credits,
                s.code
            FROM subject_results sr
            JOIN subjects s ON sr.subject_id = s.id
            JOIN presets p ON s.preset_id = p.id
            WHERE sr.user_id = ?
            ORDER BY p.year ASC, p.semester ASC
        """, (user_id,))
        
        raw_results = cursor.fetchall()
        
        if not raw_results:
            conn.close()
            flash("No results calculated yet.", "warning")
            return redirect(url_for('view_result'))

        # Group results by semester
        grouped = {}
        for row in raw_results:
            sem_key = f"{row[1]} Year - Semester {row[2]}"
            if sem_key not in grouped:
                grouped[sem_key] = {
                    'course': row[0],
                    'subjects': [],
                    'total_credits': 0,
                    'total_points': 0
                }
            grouped[sem_key]['subjects'].append({
                'name': row[3],
                'obtained': row[4],
                'max': row[5],
                'percentage': row[6],
                'grade': row[7],
                'point': row[8],
                'credits': row[9],
                'code': row[10] or ''
            })
            grouped[sem_key]['total_credits'] += row[9]
            grouped[sem_key]['total_points'] += (row[8] * row[9])

        all_credits = 0
        all_points = 0
        for sk, data in grouped.items():
            data['sgpa'] = round(data['total_points'] / data['total_credits'], 2) if data['total_credits'] > 0 else 0.0
            all_credits += data['total_credits']
            all_points += data['total_points']
        
        overall_cgpa = round(all_points / all_credits, 2) if all_credits > 0 else 0.0

        conn.close()

        # Build PDF with ReportLab
        import io
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#4f46e5'),
            spaceAfter=15,
            alignment=1 # Center
        )

        header_style = ParagraphStyle(
            'HeaderStyle',
            parent=styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#1f2937')
        )

        sem_title_style = ParagraphStyle(
            'SemTitleStyle',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor('#111827'),
            spaceBefore=15,
            spaceAfter=6
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            textColor=colors.white
        )

        table_cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#374151')
        )

        # Header Title
        story.append(Paragraph("ACADEMIC TRANSCRIPT REPORT", title_style))
        story.append(Spacer(1, 10))

        # Student Details Card Grid
        details_data = [
            [
                Paragraph(f"<b>Name:</b> {student_name}", header_style),
                Paragraph(f"<b>Roll Number:</b> {roll_number or '-'}", header_style)
            ],
            [
                Paragraph(f"<b>Enrollment Number:</b> {enrollment_number or '-'}", header_style),
                Paragraph(f"<b>Department:</b> {department or '-'}", header_style)
            ],
            [
                Paragraph(f"<b>Current Semester:</b> Semester {current_year or '-'}", header_style),
                Paragraph(f"<b>Cumulative GPA:</b> <font color='#4f46e5'><b>{overall_cgpa}</b></font>", header_style)
            ]
        ]
        details_table = Table(details_data, colWidths=[260, 260])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 15))

        # Semester Wise Subjects
        for sk, sem_data in grouped.items():
            story.append(Paragraph(f"<b>{sem_data['course']}</b> ({sk}) — SGPA: <b>{sem_data['sgpa']}</b>", sem_title_style))
            
            # Table Data
            sub_rows = [[
                Paragraph("Subject Code", table_header_style),
                Paragraph("Subject Name", table_header_style),
                Paragraph("Marks Obtained", table_header_style),
                Paragraph("Grade", table_header_style),
                Paragraph("Credits", table_header_style),
                Paragraph("Points", table_header_style),
            ]]

            for s in sem_data['subjects']:
                sub_rows.append([
                    Paragraph(s['code'], table_cell_style),
                    Paragraph(s['name'], table_cell_style),
                    Paragraph(f"{s['obtained']}/{s['max']}", table_cell_style),
                    Paragraph(s['grade'], table_cell_style),
                    Paragraph(str(s['credits']), table_cell_style),
                    Paragraph(f"{s['point'] * s['credits']:.1f}", table_cell_style)
                ])
            
            # Semester Totals Footer Row
            sub_rows.append([
                Paragraph("<b>Total</b>", table_cell_style),
                Paragraph("", table_cell_style),
                Paragraph("", table_cell_style),
                Paragraph("", table_cell_style),
                Paragraph(f"<b>{sem_data['total_credits']}</b>", table_cell_style),
                Paragraph(f"<b>{sem_data['total_points']:.1f}</b>", table_cell_style)
            ])

            sub_table = Table(sub_rows, colWidths=[90, 190, 80, 50, 50, 60])
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('TOPPADDING', (0,0), (-1,0), 6),
                ('BOTTOMPADDING', (0,1), (-1,-1), 5),
                ('TOPPADDING', (0,1), (-1,-1), 5),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f3f4f6')),
                ('GRID', (0,0), (-1,-2), 0.5, colors.HexColor('#e5e7eb')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d1d5db')),
            ]))
            story.append(sub_table)
            story.append(Spacer(1, 10))

        # Overall Transcript Summary
        story.append(Spacer(1, 15))
        summary_title_style = ParagraphStyle(
            'SummaryTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#4f46e5'),
            spaceBefore=10,
            spaceAfter=4
        )
        story.append(Paragraph("<b>Transcript Summary</b>", summary_title_style))
        summary_rows = [
            [
                Paragraph("Total Earned Credits", table_cell_style),
                Paragraph(f"<b>{all_credits}</b>", table_cell_style)
            ],
            [
                Paragraph("Overall Weighted Points", table_cell_style),
                Paragraph(f"<b>{all_points:.1f}</b>", table_cell_style)
            ],
            [
                Paragraph("Cumulative GPA (CGPA)", table_cell_style),
                Paragraph(f"<font color='#4f46e5'><b>{overall_cgpa}</b></font>", table_cell_style)
            ]
        ]
        summary_table = Table(summary_rows, colWidths=[200, 100])
        summary_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#d1d5db')),
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f9fafb')),
        ]))
        story.append(summary_table)

        doc.build(story)
        buffer.seek(0)

        from flask import send_file
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"Transcript_{student_name.replace(' ', '_')}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        import traceback
        print(f"Error compiling PDF transcript: {e}")
        print(traceback.format_exc())
        if 'conn' in locals():
            conn.close()
        flash("An error occurred generating your PDF transcript.", "error")
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

@app.route('/dev/toggle')
def toggle_dev_mode():
    # Only allow if current session is admin or if we're on localhost
    admin_emails = [e.strip() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()]
    if 'user' in session and session['user']['email'] in admin_emails:
        # In a real app, you'd update a DB or config. For this task, let's just use session.
        # But wait, DEV_MODE is global. Let's just provide a helpful message.
        return "Dev mode is controlled via .env file (DEV_MODE=true/false).", 200
    return "Unauthorized", 401

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