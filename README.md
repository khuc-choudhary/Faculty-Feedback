# Faculty Feedback System

A Flask web application for collecting and analysing student feedback on faculty.

## Features

- **Admin**: manage faculty, students and subjects; bulk-import students from Excel/CSV;
  view participation and rating reports per subject; export a full Excel report
  (subject summary, faculty summary, all anonymous responses).
- **Student**: see subjects for their department and semester; rate each faculty on
  8 criteria (1–5) with optional comments; one submission per subject.
- **Faculty**: view their own question-wise averages and anonymous comments.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

> **Windows "Application Control policy has blocked this file" error?** Smart App Control
> blocks SQLAlchemy's compiled extensions. Reinstall it as pure Python:
>
> ```powershell
> $env:DISABLE_SQLALCHEMY_CEXT = '1'
> pip install --force-reinstall --no-deps --no-binary sqlalchemy "sqlalchemy==2.1.3"
> ```

Open http://127.0.0.1:5000 and log in with the default admin account:

- Username: `admin`
- Password: `admin123`

Change this password right after your first login (**Password** in the navbar).

## Typical workflow

1. Admin adds faculty (Faculty page).
2. Admin adds subjects, setting department, semester and assigned faculty.
3. Admin adds students, one at a time or via **Bulk Import** (download the template first).
   A student sees every subject whose department and semester match their own.
4. Students log in and submit feedback.
5. Admin reviews **Reports** and downloads the Excel export.

## Project structure

```
app.py          Application factory, config, default admin seeding
models.py       SQLAlchemy models (User, Subject, Feedback) and feedback questions
routes.py       All views (auth, admin, student, faculty) and Excel import/export
templates/      Jinja2 templates (admin/, student/, faculty/)
static/         CSS and JavaScript
feedback.db     SQLite database (created on first run)
```

Set the `SECRET_KEY` (and optionally `DATABASE_URL`) environment variables before deploying.
