from app.extensions import db
from app.models import AcademicRecord, AccountRequest, FeedbackConversation, FeedbackMessage, QuestionnaireResponse, Student, User
from app.services.token_service import generate_token

from conftest import login


def test_login_redirects_admin_to_dashboard(client):
    response = login(client, "admin@test.local", "Admin@123")
    assert response.status_code == 302
    assert "/admin/dashboard" in response.headers["Location"]


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["database"] == "reachable"


def test_public_account_request_verify_and_admin_approval(app, client):
    test_ids = app.config["TEST_IDS"]

    request_response = client.post(
        "/request-account",
        data={
            "full_name": "New Student",
            "email": "newstudent@test.local",
            "phone": "0712345678",
            "requested_role": "student",
            "department_id": test_ids["department_id"],
            "course_id": test_ids["course_id"],
            "admission_no": "ADM777",
            "year_of_study": "2",
            "academic_year": "2025/2026",
            "term_type": "semester",
            "semester": "Semester 2",
        },
        follow_redirects=False,
    )
    assert request_response.status_code == 302

    with app.app_context():
        account_request = AccountRequest.query.filter_by(email="newstudent@test.local").first()
        assert account_request is not None
        token = generate_token(account_request.email, "account-request-verify")
        request_id = account_request.id

    verify_response = client.get(f"/verify-request/{token}", follow_redirects=False)
    assert verify_response.status_code == 302

    login(client, "admin@test.local", "Admin@123")
    approve_response = client.post(
        f"/admin/account-requests/{request_id}/approve",
        follow_redirects=False,
    )
    assert approve_response.status_code == 302

    with app.app_context():
        approved_user = User.query.filter_by(email="newstudent@test.local").first()
        linked_student = Student.query.filter_by(admission_no="ADM777").first()
        assert approved_user is not None
        assert linked_student is not None
        assert linked_student.user_id == approved_user.id


def test_admin_can_create_learner_and_lecturer_can_access_dashboard(app, client):
    test_ids = app.config["TEST_IDS"]
    login(client, "admin@test.local", "Admin@123")

    create_response = client.post(
        "/students/new",
        data={
            "admission_no": "ADM900",
            "full_name": "Created Learner",
            "email": "created@test.local",
            "phone": "0799999999",
            "department_id": test_ids["department_id"],
            "course_id": test_ids["course_id"],
            "year_of_study": "1",
            "academic_year": "2025/2026",
            "term_type": "semester",
            "semester": "Semester 1",
            "unit_ids": [str(unit_id) for unit_id in test_ids["unit_ids"][:2]],
            "temporary_password": "TempPass@123",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    client.get("/auth/logout", follow_redirects=False)
    lecturer_login = login(client, "lecturer@test.local", "Lecturer@123")
    assert lecturer_login.status_code == 302

    dashboard_response = client.get("/lecturer/dashboard")
    learners_response = client.get("/students/")
    records_response = client.get("/lecturer/academic-records")
    assert dashboard_response.status_code == 200
    assert learners_response.status_code == 200
    assert records_response.status_code == 200
    assert b"Created Learner" in learners_response.data


def test_student_dashboard_access(client):
    login(client, "student@test.local", "Student@123")

    dashboard_response = client.get("/student/dashboard")
    history_response = client.get("/student/prediction-history")
    profile_response = client.get("/student/profile")
    report_response = client.get("/student/report")
    questionnaire_form_response = client.get("/student/questionnaire/new")
    change_password_response = client.get("/auth/change-password")

    assert dashboard_response.status_code == 200
    assert history_response.status_code == 200
    assert profile_response.status_code == 200
    assert report_response.status_code == 200
    assert questionnaire_form_response.status_code == 200
    assert change_password_response.status_code == 200
    assert b"Save New Password" in change_password_response.data


def test_student_can_submit_own_questionnaire(app, client):
    login(client, "student@test.local", "Student@123")

    response = client.post(
        "/student/questionnaire/new",
        data={
            "academic_year": "2025/2026",
            "term_type": "semester",
            "term_name": "Semester 1",
            "attendance_frequency": "Often",
            "coursework_on_time": "Often",
            "main_challenge": "Time Management",
            "early_warning_helpful": "Yes",
            "study_hours_per_week": "10",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        saved = QuestionnaireResponse.query.filter_by(student_id=app.config["TEST_IDS"]["student_id"]).first()
        assert saved is not None
        assert saved.term_name == "Semester 1"


def test_academic_record_requires_specific_unit(app, client):
    login(client, "admin@test.local", "Admin@123")
    test_ids = app.config["TEST_IDS"]

    response = client.post(
        f"/students/{test_ids['student_id']}/academic/new",
        data={
            "unit_id": str(test_ids["unit_ids"][0]),
            "academic_year": "2025/2026",
            "term_type": "semester",
            "term_name": "Semester 1",
            "attendance_percent": "88",
            "assignment_mark": "12",
            "cat_mark": "20",
            "exam_mark": "55",
            "teacher_comment": "Strong improvement.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        record = AcademicRecord.query.filter_by(student_id=test_ids["student_id"]).first()
        assert record is not None
        assert record.unit_id == test_ids["unit_ids"][0]


def test_notification_center_and_bulk_import(app, client):
    login(client, "admin@test.local", "Admin@123")

    notifications_response = client.get("/notifications")
    assert notifications_response.status_code == 200

    learner_csv = (
        "admission_no,full_name,department_code,course_code,year_of_study,semester,email\n"
        "ADM901,Bulk Learner,COMP,IT01,2,Semester 2,bulk@test.local\n"
    ).encode("utf-8")

    import io
    import_response = client.post(
        "/admin/imports",
        data={
            "import_type": "learners",
            "csv_file": (io.BytesIO(learner_csv), "learners.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert import_response.status_code == 302

    with app.app_context():
        imported_student = Student.query.filter_by(admission_no="ADM901").first()
        assert imported_student is not None


def test_admin_export_center_and_model_history(app, client):
    login(client, "admin@test.local", "Admin@123")

    export_page = client.get("/admin/exports")
    learner_export = client.get("/admin/exports?dataset=learners")
    model_response = client.post("/admin/ml", follow_redirects=False)

    assert export_page.status_code == 200
    assert learner_export.status_code == 200
    assert learner_export.mimetype == "text/csv"
    assert b"admission_no,full_name" in learner_export.data
    assert model_response.status_code == 302

    ml_page = client.get("/admin/ml")
    assert ml_page.status_code == 200
    assert b"Recent Model Runs" in ml_page.data
    assert b"Needs More Data" in ml_page.data


def test_support_conversation_admin_reply_and_closed_lock(app, client):
    login(client, "student@test.local", "Student@123")
    create_response = client.post(
        "/support",
        data={
            "sender_name": "Student User",
            "sender_email": "student@test.local",
            "support_type": "General Inquiry",
            "message": "I need help with my account.",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    with app.app_context():
        conversation = FeedbackConversation.query.order_by(FeedbackConversation.id.desc()).first()
        assert conversation is not None
        conversation_id = conversation.id
        assert FeedbackMessage.query.filter_by(conversation_id=conversation_id).count() == 1

    client.get("/auth/logout", follow_redirects=False)
    login(client, "admin@test.local", "Admin@123")

    reply_response = client.post(
        f"/admin/feedback/{conversation_id}/reply",
        data={"body": "We have received your request."},
        follow_redirects=False,
    )
    close_response = client.post(
        f"/admin/feedback/{conversation_id}/close",
        follow_redirects=False,
    )
    assert reply_response.status_code == 302
    assert close_response.status_code == 302

    client.get("/auth/logout", follow_redirects=False)
    login(client, "student@test.local", "Student@123")
    locked_response = client.post(
        f"/my-support/{conversation_id}/reply",
        data={"body": "Trying to reply after closure."},
        follow_redirects=True,
    )

    assert locked_response.status_code == 200
    assert b"can no longer receive new messages" in locked_response.data

    with app.app_context():
        count = FeedbackMessage.query.filter_by(conversation_id=conversation_id).count()
        assert count == 2
        db.session.remove()
