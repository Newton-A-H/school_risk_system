# EduRisk AI - Academic Risk Prediction and Advisory System

A professional Flask + SQL Server school system built around Kenyan school usage. It uses marks instead of GPA, stores all operational data in SQL, includes the proposal questionnaire, and provides AI-driven risk prediction and advisory support.

## Core professional features
- SQL Server only for live system data
- Responsive Bootstrap 5 interface with custom styling
- Questionnaire-aware risk assessment
- Proper ML workflow: train/test split, cross-validation, hyperparameter tuning, probability calibration, threshold tuning, explainability, saved artifacts
- School-ready learner intake and prediction pages
- Chart.js dashboard with corrected chart configuration
- Cloud-ready structure for later deployment

## Folder structure
```text
school_risk_system/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── forms.py
│   ├── models.py
│   ├── auth/
│   │   └── routes.py
│   ├── main/
│   │   └── routes.py
│   ├── students/
│   │   └── routes.py
│   ├── ml/
│   │   ├── predictor.py
│   │   └── training.py
│   ├── services/
│   │   ├── advisory.py
│   │   └── charts.py
│   ├── static/
│   │   ├── css/app.css
│   │   └── js/dashboard.js
│   └── templates/
│       ├── base.html
│       ├── auth/login.html
│       ├── main/home.html
│       ├── main/dashboard.html
│       └── students/
│           ├── detail.html
│           ├── index.html
│           └── new.html
├── sql/
│   ├── schema_mssql.sql
│   └── seed.sql
├── .env.example
├── requirements.txt
├── README.md
└── run.py
```

## How to use with SSMS and SQL Server
1. Open SQL Server Management Studio.
2. Connect to your local SQL Server instance.
3. Open `sql/schema_mssql.sql` and execute it. This creates `AcademicRiskDB` and all tables.
4. In Windows search, open **ODBC Data Sources (64-bit)** and confirm you have **ODBC Driver 17 for SQL Server** or newer installed.
5. Create a Python virtual environment and install packages:
   - `python -m venv venv`
   - `venv\Scripts\activate`
   - `pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and update `DATABASE_URL` with your SQL Server username, password, server name, and database.
7. Start the app with `python run.py`.
8. Open the site in your browser.

## Create first real admin password
Because Werkzeug hashes are generated in Python, use Flask shell after first run:
```python
from app import create_app
from app.extensions import db
from app.models import User
app = create_app()
with app.app_context():
    admin = User(full_name='System Administrator', email='admin@school.local', role='admin')
    admin.set_password('Admin@12345')
    db.session.add(admin)
    db.session.commit()
```
Then sign in with `admin@school.local`.

## Notes about the questionnaire
This system uses the proposal questionnaire items directly:
- How often do you attend classes?
- Do you submit coursework on time?
- What challenge affects your academic performance most?
- Would early academic warnings help you improve?
These are combined with marks, attendance, coursework, exams, and study hours.

## Why this is stronger than the older version
- No JSON storage
- No GPA assumption
- Better dashboard charts
- Professional UI and layout
- Proper machine learning lifecycle
- Easier migration to cloud hosting later
