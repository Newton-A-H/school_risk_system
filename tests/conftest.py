from app import create_app
from app.extensions import db
from app.models import Course, Department, Student, Unit, User
from app.services.academic import get_default_academic_year


def _create_user(full_name, email, role, password, department_id=None):
    user = User(
        full_name=full_name,
        email=email,
        role=role,
        department_id=department_id,
        is_active_account=True,
        is_verified=True,
        verification_token=None,
        must_change_password=False,
    )
    user.set_password(password)
    return user


def login(client, email, password):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def pytest_configure():
    import os
    os.environ.setdefault("MAIL_ENABLED", "false")


import pytest


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "BOOTSTRAP_DATABASE": False,
            "VALIDATE_STARTUP": False,
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        }
    )

    with app.app_context():
        db.create_all()

        department = Department(name="Computing", code="COMP")
        db.session.add(department)
        db.session.flush()

        course = Course(
            name="Information Technology",
            code="IT01",
            department_id=department.id,
            program_level="Diploma",
        )
        db.session.add(course)
        db.session.flush()

        units = [
            Unit(course_id=course.id, name="Introduction to Computing", code="ICT101"),
            Unit(course_id=course.id, name="Database Systems", code="ICT102"),
            Unit(course_id=course.id, name="Web Development", code="ICT103"),
        ]
        db.session.add_all(units)

        admin = _create_user("Admin User", "admin@test.local", "admin", "Admin@123")
        lecturer = _create_user(
            "Lecturer User",
            "lecturer@test.local",
            "lecturer",
            "Lecturer@123",
            department_id=department.id,
        )
        student_user = _create_user("Student User", "student@test.local", "student", "Student@123")
        db.session.add_all([admin, lecturer, student_user])
        db.session.flush()

        student = Student(
            admission_no="ADM001",
            full_name="Student User",
            email="student@test.local",
            phone="0700000000",
            gender="Female",
            school_name="Demo School",
            department_id=department.id,
            course_id=course.id,
            year_of_study=1,
            semester="Semester 1",
            term_type="semester",
            academic_year=get_default_academic_year(),
            user_id=student_user.id,
            lecturer_user_id=lecturer.id,
        )
        db.session.add(student)
        db.session.commit()

        app.config["TEST_IDS"] = {
            "department_id": department.id,
            "course_id": course.id,
            "unit_ids": [unit.id for unit in units],
            "admin_id": admin.id,
            "lecturer_id": lecturer.id,
            "student_user_id": student_user.id,
            "student_id": student.id,
        }

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
