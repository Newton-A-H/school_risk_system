# EduSentinel AI

EduSentinel AI is a Flask + PostgreSQL academic risk monitoring platform with role-based experiences for admins, lecturers, and students. It combines learner records, semester questionnaires, prediction history, intervention tracking, support conversations, and model-management pages in one school-focused system.

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
3. Copy `.env.example` to `.env` and fill in your PostgreSQL and mail settings.
4. Start the app.
   ```powershell
   python run.py
   ```
5. Open the local URL shown by Flask in your browser.

## Environment variables

Minimum required values:

```env
SECRET_KEY=change-me
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/academic_risk_db
ARTIFACTS_DIR=artifacts
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

Render deployment values:

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
ARTIFACTS_DIR=/app/artifacts
SESSION_COOKIE_SECURE=true
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

The test suite uses SQLite and disables normal bootstrap side effects automatically.

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
- Confirm `DATABASE_URL` points to the production PostgreSQL instance
- Set `SESSION_COOKIE_SECURE=true` behind HTTPS
- Configure mail credentials if email delivery is required
- Run with a production WSGI server such as `gunicorn` or your Windows hosting equivalent
- Verify the `artifacts/` folder contains the trained model files before relying on AI predictions
- Create the first admin account and test each role login

## Render deployment

This repository is prepared for Render using a Docker web service and PostgreSQL.

Files added for deployment:

- `Dockerfile`
- `startup.sh`
- `wsgi.py`
- `render.yaml`

### Recommended Render setup

1. Create a new Render Web Service from this GitHub repository.
2. Let Render build from the included `Dockerfile`.
3. Attach a persistent disk mounted at `/app/artifacts`.
4. Create Render Postgres or use another reachable PostgreSQL provider such as Neon.
5. Set the required environment variables in Render.

### Render environment variables

Set these values in Render:

- `SECRET_KEY`
- `DATABASE_URL`
- `ARTIFACTS_DIR=/app/artifacts`
- `BOOTSTRAP_DATABASE=true`
- `VALIDATE_STARTUP=true`
- `SESSION_COOKIE_SECURE=true`
- `MAIL_ENABLED`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_DEFAULT_SENDER`

Typical PostgreSQL connection string format:

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

Examples:

```env
DATABASE_URL=postgresql+psycopg://postgres:secret123@dpg-abc123-a.oregon-postgres.render.com:5432/academic_risk_db
DATABASE_URL=postgresql+psycopg://postgres:secret123@ep-cool-name.us-east-1.aws.neon.tech/academic_risk_db?sslmode=require
```

### Render Blueprint

The repository now includes `render.yaml`, so Render can import the service configuration directly from GitHub.

Important note:
- Keep the persistent disk mounted at `/app/artifacts` so trained model files and model history survive redeploys.

### Deployment flow

1. Push this repo to GitHub.
2. In Render, create a new Blueprint or Web Service from the repository.
3. Create the PostgreSQL database and copy its external connection string.
4. Confirm the Docker service settings and persistent disk mount.
5. Add the environment variables listed above.
6. Trigger the first deploy.
7. After deployment, check:
   - `https://<your-render-service>.onrender.com/health`
   - admin login
   - database connectivity
   - model artifact persistence under `/app/artifacts`

### Notes for production

- The health endpoint is available at `/health` and `/healthz`.
- `startup.sh` uses `gunicorn` and listens on the `PORT` value that Render provides.
- If you retrain the model in production, keep `ARTIFACTS_DIR=/app/artifacts` and attach the persistent disk there.

## PostgreSQL migration notes

- The app now connects with the `postgresql+psycopg` SQLAlchemy dialect.
- The SQL Server-specific bootstrap logic has been replaced with ORM-driven schema creation via `db.create_all()`.
- The old SQL scripts in `sql/` are kept only as legacy reference and should not be reused as PostgreSQL scripts without conversion.
- Existing Alembic migration files were written for SQL Server-era schema history; for a clean PostgreSQL deployment, start from the current models and generate new PostgreSQL-safe migrations if you choose to use Alembic later.

## Notes

- When the trained model artifact is missing, the app falls back to its starter rule-based prediction path.
- `AGENTS.md` contains repository-specific guidance for future Codex sessions.
- Database bootstrap is now ORM-based and should stay enabled for normal PostgreSQL development unless you are running tests.
