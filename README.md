# CGPA Calculator System

This is a single-folder monolithic web application for a college CGPA system.

## Features

- Google OAuth for authentication
- Admin and Student roles
- Preset system for subjects and components
- CGPA calculation
- PDF export of results (to be implemented)
- Grading rule management
- Student record management

## Project Structure

```
cgpa_system/
│
├── app.py
├── database.db
├── database.py
├── requirements.txt
├── templates/
│   ├── login.html
│   ├── student.html
│   ├── admin.html
│   ├── result.html
│   ├── additional_info.html
│   ├── edit_preset.html
│   ├── manage_subjects.html
│   ├── edit_subject.html
│   ├── view_students.html
│   ├── edit_student_record.html
│   └── manage_grading_rules.html
│
└── static/
    ├── css/
    │   └── style.css
    ├── js/
    └── images/
        └── google-login-button.png
```

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/cgpa-calculator.git
   ```
2. **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3. **Set up Google OAuth:**
    - Go to the [Google API Console](https://console.developers.google.com/).
    - Create a new project.
    - Go to **Credentials** and create an **OAuth client ID**.
    - Select **Web application** as the application type.
    - Add `http://127.0.0.1:5000/authorize` to the **Authorized redirect URIs**.
    - Copy the **Client ID** and **Client Secret**.
    - Open `app.py` and replace `YOUR_GOOGLE_CLIENT_ID` and `YOUR_GOOGLE_CLIENT_SECRET` with your actual credentials.
4. **Run the database script:**
    ```bash
    python database.py
    ```
5. **Run the application:**
    ```bash
    python app.py
    ```
6. **Open your browser and go to `http://127.0.0.1:5000`**

## Admin

The admin is identified by the email `singh02.rushabh@gmail.com`. If you log in with this email, you will be redirected to the admin dashboard.

The admin can:
- Create, edit, and delete presets.
- Manage subjects and components for each preset.
- View all students and their records.
- Edit and delete student records.
- Manage the grading rules.

## Student

Any other user who logs in will be a student. After the first login, the user will be asked to provide their name and roll number.

The student can:
- Select their academic details.
- Load the subjects for the selected preset.
- Enter their marks for each component.
- Calculate their CGPA.
- View their result.
- Download their result as a PDF (to be implemented).

## PDF Download

The PDF download functionality is not yet implemented. It will be added in a future version.

## Grading Rule Management

The admin can manage the grading rules from the admin dashboard. The default grading rules are:

| % Range | Grade | Grade Point |
|---|---|---|
| 90–100 | O | 10 |
| 80–89 | A+ | 9 |
| 70–79 | A | 8 |
| 60–69 | B+ | 7 |
| 50–59 | B | 6 |
| 40–49 | C | 5 |
| 0–39 | F | 0 |