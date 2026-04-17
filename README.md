# 🎓 CGPA Pro System

<div align="center">

![CGPA Pro](https://img.shields.io/badge/CGPA%20Pro-v1.0-6C63FF?style=for-the-badge&logo=graduation-cap)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**A full-stack CGPA & grade management platform for TSEC Mumbai students.**  
Built with Flask, Google OAuth, and a glassmorphism-styled UI.

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [User Roles](#-user-roles)
- [Developer Mode](#-developer-mode)
- [Admin Guide](#-admin-guide)
- [Student Guide](#-student-guide)
- [Database Management](#-database-management)
- [Grading System](#-grading-system)
- [Contributing](#-contributing)

---

## 🌟 Overview

**CGPA Pro System** is a secure, institution-specific academic management web application built for [Thadomal Shahani Engineering College (TSEC), Mumbai](https://tsec.edu). It enables administrators to configure class presets, subjects, and grading rules, while students can log in with their college Google account to enter marks and instantly see their SGPA/CGPA breakdowns.

> 🔒 Login is restricted exclusively to `@tsecmumbai.in` email addresses (plus configurable admin emails).

---

## ✨ Features

### 🔐 Authentication
- **Google OAuth 2.0** via Authlib — zero-password, institution-enforced login.
- Strict **domain restriction** to `@tsecmumbai.in`; unauthorized users see a dedicated rejection page.
- **Admin bypass** via a configurable environment variable list (`ADMIN_EMAILS`).
- **Developer Mode** for local testing without Google credentials.

### 🛠️ Admin Panel
- Create, edit, duplicate, and delete **class presets** (Academic Year → Course → Department → Year → Division → Semester).
- Manage **subjects** per preset: name, subject code, credit weightage.
- Define **assessment components** per subject (e.g., UT1, UT2, End-Sem) with maximum marks.
- Configure **custom grading rules** (percentage bands mapped to grade letters and grade points).
- View all registered **students** and their complete result history.
- **Promote students** between academic years.
- Download/upload/migrate the **SQLite database** directly from the UI.
- Export a **master sheet** of all student results.

### 🎒 Student Dashboard
- Auto-filtered class list based on the student's registered **department and current year**.
- Enter marks per component per subject in a single form.
- Instant **SGPA calculation** per semester and **cumulative CGPA** across all semesters.
- Persistent results: marks are saved and reloaded on every visit.
- View a **detailed result breakdown** with grade, grade point, and subject-wise percentage.

### 🌗 Theming & UX
- Glassmorphism-styled UI with a **dark/light mode** toggle (persisted via session).
- Responsive layout with flash notifications for all actions.
- A prominent red **DEV** badge in the navbar when Developer Mode is active.

---

## 🛠️ Tech Stack

| Category         | Technology                                   |
|------------------|----------------------------------------------|
| Backend          | Python 3.8+, Flask 3.x                       |
| Authentication   | Google OAuth 2.0 (Authlib)                   |
| Database         | SQLite 3 (via Python `sqlite3` module)        |
| Templating       | Jinja2 (Flask built-in)                      |
| Styling          | Vanilla CSS + Glassmorphism Design           |
| Environment Mgmt | python-dotenv                                |
| HTTP Sessions    | Flask server-side sessions                   |

---

## 📁 Project Structure

```
cgpa_system/
├── app.py                      # Main Flask application & all route handlers
├── database.py                 # DB connection + table creation + default seed data
├── database.md                 # Human-readable database schema documentation
│
├── migration_tools/            # CLI and in-app database migration utilities
│   └── migrate_database.py
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html               # Shared layout (nav, flash messages, theme toggle)
│   ├── login.html              # Google login / Dev Mode login form
│   ├── additional_info.html    # New student onboarding form
│   ├── admin.html              # Admin dashboard (presets, DB management)
│   ├── manage_subjects.html    # Subject & component manager per preset
│   ├── manage_grading_rules.html
│   ├── student.html            # Student dashboard (mark entry)
│   ├── result.html             # Semester-wise SGPA & CGPA result viewer
│   ├── view_students.html      # Admin view of all registered students
│   ├── admin_student_results.html
│   ├── master_sheet.html       # Full exportable result table
│   ├── promote_students.html
│   ├── view_profile.html
│   ├── edit_preset.html
│   ├── edit_subject.html
│   ├── edit_student_record.html
│   ├── dev_login.html
│   └── unauthorized.html
│
├── static/                     # CSS, JS, image assets
├── .env                        # Local environment variables (never commit!)
├── .gitignore
├── requirements.txt
└── database.db                 # SQLite database (auto-created on first run)
```

---

## 🗄️ Database Schema

```
users           — Stores student/admin profiles (email, name, roll, dept, year)
presets         — Class configurations (AY, course, dept, year, division, sem)
subjects        — Subjects linked to a preset (name, code, credits)
components      — Assessment components per subject (name, max_marks)
student_marks   — Per-student, per-component marks (UNIQUE user+component)
subject_results — Computed grade/percentage per student per subject
cgpa            — Cumulative CGPA per student (UNIQUE per user)
grading_rules   — Configurable percentage → grade → grade_point mapping
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **pip**
- A **Google Cloud project** with OAuth 2.0 credentials (for production use)
- A Chromium-based browser (Chrome/Edge) recommended

### Installation

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd cgpa_system

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (see section below)
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux

# 5. Run the application
python app.py
```

The app starts at **`http://127.0.0.1:5000`**.

> ✅ The database (`database.db`) and all tables are **auto-created** on first run. No manual DB setup needed.

### Available Scripts (Utility)

| Script                     | Purpose                                              |
|----------------------------|------------------------------------------------------|
| `python app.py`            | Start the Flask development server                   |
| `python database.py`       | Initialise / re-seed the database manually           |
| `python recalculate_grades.py` | Recalculate grades for all students after rule changes |
| `python list_presets.py`   | CLI dump of all presets                              |
| `python fix_departments.py`| Repair legacy department data inconsistencies        |

---

## 🔑 Environment Variables

Create a `.env` file in the project root:

```ini
# Flask session security key — use a long random string in production
FLASK_SECRET_KEY=your_super_secret_key_here

# Google OAuth 2.0 credentials (from Google Cloud Console)
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Comma-separated list of admin email addresses (can include non-tsec emails)
ADMIN_EMAILS=admin@example.com,another.admin@tsecmumbai.in

# Developer Mode: bypasses Google login for local testing
# Set to "false" or remove entirely for production
DEV_MODE=true
```

> ⚠️ **Never commit `.env` to version control.** It is already included in `.gitignore`.

---

## 👥 User Roles

| Role      | Access                                                           |
|-----------|------------------------------------------------------------------|
| **Admin** | Full access: manage presets, subjects, grading rules, students  |
| **Student** | View own dashboard, enter marks, view results, edit profile   |

Role is determined at login by comparing the authenticated email against `ADMIN_EMAILS` in the environment. Admins can be outside the `@tsecmumbai.in` domain.

---

## 🧑‍💻 Developer Mode

Developer Mode lets you test the full application without setting up Google OAuth credentials.

1. Set `DEV_MODE=true` in your `.env` file.
2. Navigate to `http://127.0.0.1:5000/login`.
3. Enter **any email address** and a display name to log in.
   - Use an email listed in `ADMIN_EMAILS` to log in as Admin.
   - Use any `@tsecmumbai.in` email (or any email in DEV mode) to log in as Student.
4. A red **DEV** badge appears in the top navigation bar as a reminder.

> 🔴 **Always set `DEV_MODE=false` before deploying to production.**

---

## 🛡️ Admin Guide

### Managing Class Presets

1. Go to the **Admin Dashboard** (`/admin`).
2. Click **Add New Preset** → fill in Academic Year, Department, Year (FE/SE/TE/BE), Division, and Semester.
3. Click **Manage Subjects** on any preset to add subjects with their codes and credit values.
4. Within each subject, add **Assessment Components** (e.g., UT1 = 30 marks, End-Sem = 70 marks).
5. Use **Duplicate** to clone an entire preset (including subjects and components) for a new division.

### Managing Grading Rules

Navigate to **Grading Rules** (`/admin/grading_rules`) to view or customise the percentage-to-grade mapping.

### Database Management

From the Admin Dashboard:
- **Download DB** — Export the live `database.db` file for backup.
- **Restore DB** — Upload a previously downloaded backup to replace the live database.
- **Migrate DB** — Upload an old-format database; the system migrates it to the current schema and auto-backs up the existing one.

---

## 🎒 Student Guide

1. **Log in** with your `@tsecmumbai.in` Google account.
2. On first login, complete the **profile form** (Name, Roll No., Enrollment No., Department, Academic Year, Current Year).
3. On the **Student Dashboard**, your relevant class presets are automatically filtered by your year and department.
4. Select your class → enter marks for each component → click **Calculate**.
5. Your **SGPA per semester** and **overall CGPA** are displayed on the Results page.

---

## 📊 Grading System

The default grading scale follows the **University of Mumbai** grading system:

| Percentage Range | Grade | Grade Point |
|-----------------|-------|-------------|
| 90 – 100        | O     | 10          |
| 80 – 89.99      | A+    | 9           |
| 70 – 79.99      | A     | 8           |
| 60 – 69.99      | B+    | 7           |
| 50 – 59.99      | B     | 6           |
| 40 – 49.99      | C     | 5           |
| 0  – 39.99      | F     | 0           |

Admins can fully customise these rules from the Admin Dashboard without touching code.

**SGPA Formula:**
```
SGPA = Σ(Grade Point × Credits) / Σ(Credits)   [for a single semester]
```

**CGPA Formula:**
```
CGPA = Σ(Grade Point × Credits) / Σ(Credits)   [across all semesters]
```

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and test thoroughly in Developer Mode.
4. Commit with a descriptive message: `git commit -m "feat: describe your change"`
5. Push and open a Pull Request.

Please ensure:
- No sensitive credentials are committed (check `.env` is gitignored).
- All new routes include proper session/admin checks.
- DB schema changes are reflected in `database.py` and `database.md`.

---

## 📄 License

This project is licensed under the **MIT License**.

---

<div align="center">

Built with ❤️ for **TSEC Mumbai** students  
*Making academic tracking effortless.*

</div>