# EduSentinel AI

EduSentinel AI is a Flask + SQL Server academic risk monitoring platform with role-based experiences for admins, lecturers, and students. It combines learner records, semester questionnaires, prediction history, intervention tracking, support conversations, and model-management pages in one school-focused system.

## What the current build includes

- Public account request flow with email verification and admin approval
- Admin, lecturer, and student role-based dashboards
- Learner intake, academic-record capture, questionnaire capture, and semester prediction flow
- Intervention logs with follow-up tracking
- Support desk with threaded conversations, unread badges, and close/reopen controls
- Student self-service pages for profile, academic history, questionnaire history, prediction history, and interventions
- Admin reporting with filters and CSV export
- Admin ML control page with readiness metrics, feature importance, and retrain action
- Audit trail for key admin/support/account actions

## Project structure

```text
school_risk_system/
|-- app/
|   |-- __init__.py
|   |-- config.py
|   |-- models.py
|   |-- auth/
|   |-- admin/
|   |-- lecturer/
|   |-- main/
|   |-- student_portal/
|   |-- students/
|   |-- ml/
|   |-- services/
|   |-- static/
|   `-- templates/
|-- artifacts/
|-- migrations/
|-- sql/
|-- tests/
|-- AGENTS.md
|-- requirements.txt
`-- run.py
```

## Local setup

1. Create and activate a virtual environment.
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
2. Install dependencies.
   ```powershell
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your SQL Server and mail settings.
4. Start the app.
   ```powershell
   python run.py
   ```
5. Open the local URL shown by Flask in your browser.

## Environment variables

Minimum required values:

```env
SECRET_KEY=change-me
DATABASE_URL=mssql+pyodbc://sa:YourPassword123@localhost/AcademicRiskDB?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```

Optional operational settings:

```env
MAIL_ENABLED=false
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@edusentinel.ai
BOOTSTRAP_DATABASE=true
VALIDATE_STARTUP=true
SESSION_COOKIE_SECURE=false
```

## First admin setup

After the database is reachable, create the first admin from a Python shell:

```python
from app import create_app
from app.extensions import db
from app.models import User

app = create_app()
with app.app_context():
    admin = User(full_name="System Administrator", email="admin@school.local", role="admin")
    admin.set_password("Admin@12345")
    db.session.add(admin)
    db.session.commit()
```

## Running tests

The test suite uses SQLite and disables SQL Server bootstrap automatically.

```powershell
pytest
```

Covered flows include:

- login redirect by role
- public account request, verification, and approval
- learner creation
- lecturer dashboard access
- student dashboard access
- support conversation creation, admin reply, and closed-thread lock

## Deployment checklist

- Set a strong non-default `SECRET_KEY`
- Confirm `DATABASE_URL` points to the production SQL Server instance
- Install the ODBC SQL Server driver on the host
- Set `SESSION_COOKIE_SECURE=true` behind HTTPS
- Configure mail credentials if email delivery is required
- Run with a production WSGI server such as `gunicorn` or your Windows hosting equivalent
- Verify the `artifacts/` folder contains the trained model files before relying on AI predictions
- Create the first admin account and test each role login

## Notes

- When the trained model artifact is missing, the app falls back to its starter rule-based prediction path.
- `AGENTS.md` contains repository-specific guidance for future Codex sessions.
- Database bootstrap is intended for the SQL Server environment and should stay enabled for normal local development unless you are running tests.
