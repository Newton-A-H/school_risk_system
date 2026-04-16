# AGENTS.md

## Project
EduSentinel AI is a Flask + PostgreSQL academic risk monitoring system with role-based interfaces for admin, lecturer, and student users.

## Architecture
- Flask app package: `app/`
- Blueprints:
  - `app/auth`
  - `app/main`
  - `app/admin`
  - `app/lecturer`
  - `app/students`
  - `app/student_portal`
- Templates live in `app/templates/`
- Static assets live in `app/static/`
- SQLAlchemy models live in `app/models.py`
- ML code lives in `app/ml/`
- Advisory/business logic lives in `app/services/`

## Rules
- Prefer full-file rewrites over fragile partial edits when files have drifted.
- Keep route names, template names, and model fields aligned.
- Do not introduce template variables unless every render path passes them.
- Do not invent new database columns without also specifying how the PostgreSQL schema should be updated.
- Keep Bootstrap-based styling consistent with current UI.
- Protect admin, lecturer, and student routes correctly.
- Lecturer access must stay scoped to department.
- Student access must stay scoped to the linked learner account.
- Closed support conversations must be read-only for non-admin users.

## Before editing
- Read the relevant route, model, and template files first.
- Check for schema drift between SQLAlchemy models, bootstrap logic, and migration assumptions.
- Identify likely breakpoints from earlier changes.

## After editing
- Verify imports are correct.
- Verify endpoint names used in templates actually exist.
- Verify context variables used in templates are always passed.
- Verify foreign key assumptions still match models.
- Suggest SQL updates when schema changes are required.

## Done means
- Code is internally consistent.
- No obvious broken route-template links remain.
- No undefined template variables remain.
- New features fit existing role structure and UI.
