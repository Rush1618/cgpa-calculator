# CGPA Calculator System

This is a single-folder monolithic web application for a college CGPA system.

## Features

- Firebase Google OAuth for authentication
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
├── .env                  # Contains Firebase configuration and service account key path
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
3. **Set up Firebase Project:**
    - Go to the [Firebase Console](https://console.firebase.google.com/).
    - Create a new project (e.g., `cgpa-calc-bc705`).

4. **Enable Google Sign-In:**
    - In your Firebase project, navigate to **Authentication** > **Sign-in method**.
    - Enable the **Google** sign-in provider.

5. **Get Web App Firebase Configuration:**
    - In your Firebase project, go to **Project settings** (the gear icon).
    - Under the "Your apps" section, click on the **Web** icon (`</>`) to add a new web app.
    - Follow the steps to register your app.
    - Copy the `firebaseConfig` object provided.
    - **Update `cgpa_system/.env`** with these values:
      ```
      VITE_FIREBASE_API_KEY="YOUR_API_KEY"
      VITE_FIREBASE_AUTH_DOMAIN="YOUR_AUTH_DOMAIN"
      VITE_FIREBASE_PROJECT_ID="YOUR_PROJECT_ID"
      VITE_FIREBASE_STORAGE_BUCKET="YOUR_STORAGE_BUCKET"
      VITE_FIREBASE_MESSAGING_SENDER_ID="YOUR_MESSAGING_SENDER_ID"
      VITE_FIREBASE_APP_ID="YOUR_APP_ID"
      VITE_FIREBASE_MEASUREMENT_ID="YOUR_MEASUREMENT_ID"
      ```
      (Replace `YOUR_...` with the actual values from your Firebase config).

6. **Create Firebase Service Account Key (for Flask Backend):**
    - In your Firebase project, go to **Project settings** > **Service accounts**.
    - Click on **Generate new private key** and confirm.
    - A JSON file will be downloaded. Rename it to `serviceAccountKey.json` (or any other name) and place it in the `cgpa_system` directory.
    - **Update `cgpa_system/.env`** with the path to this file:
      ```
      FIREBASE_SERVICE_ACCOUNT_KEY_PATH="serviceAccountKey.json" # Or the path if you placed it elsewhere
      ```

7. **Run the database script:**
    ```bash
    python database.py
    ```
8. **Run the application:**
    ```bash
    python app.py
    ```
9. **Open your browser and go to `http://127.0.0.1:5000`**

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
