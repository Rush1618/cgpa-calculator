# CGPA Pro System

A premium, glassmorphism-styled CGPA Calculator with robust Admin management, Google Authentication, and Student features.

## Features
- **Strict Authentication**: Google Login restricted to `@tsecmumbai.in` domains.
- **Admin Dashboard**: Manage class presets, subjects, grading rules, and promote students.
- **Student Dashboard**: View tailored subjects, enter marks, and see detailed result breakdowns.
- **Smart Filtering**: Automatically filters classes based on your current year (FE/SE/TE/BE).
- **Data Integrity**: Prevents duplicate records and maintains consistent student profiles.
- **Developer Mode**: Built-in bypass for testing without Google Credentials.

## Setup Instructions

### 1. Prerequisites
- Python 3.8+
- SQLite3

### 2. Installation
```bash
# Clone the repository
git clone <your-repo-url>
cd cgpa_system

# Install dependencies
pip install flask authlib requests python-dotenv
```

### 3. Configuration (.env)
Create a `.env` file in the root directory:
```ini
FLASK_SECRET_KEY=your_super_secret_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
# Optional: Enable Developer Mode (Bbypass Login)
DEV_MODE=true
```

### 4. Database Initialization
The application automatically creates `database.db` on first run.
To migrate an old database:
```bash
python migration_tools/migrate_database.py old_backup.db
```

### 5. Running the App
```bash
python app.py
```
Access the app at `http://127.0.0.1:5000`.

## Developer Mode
- Set `DEV_MODE=true` in `.env`.
- Go to `/dev_login` to log in as Admin or Student without Google Auth.
- A red "DEV" badge will appear in the navigation bar.

## Admin Credentials
- Default Admin Email: `singh02.rushabh@gmail.com` (Change `ADMIN_EMAIL` in `app.py` if needed).