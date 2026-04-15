from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    code = db.Column(db.String(30), nullable=False, unique=True)

    courses = db.relationship("Course", backref="department", lazy=True)
    students = db.relationship("Student", backref="department", lazy=True)
    users = db.relationship("User", backref="department", lazy=True)
    account_requests = db.relationship("AccountRequest", backref="department", lazy=True)


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    code = db.Column(db.String(30), nullable=False, unique=True)
    program_level = db.Column(db.String(30), nullable=False, default="Diploma")

    students = db.relationship("Student", backref="course", lazy=True)
    account_requests = db.relationship("AccountRequest", backref="course", lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(30), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(255), nullable=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    verified_records = db.relationship(
        "AcademicRecord",
        backref="verifier",
        lazy=True,
        foreign_keys="AcademicRecord.verified_by",
    )

    created_predictions = db.relationship(
        "RiskPrediction",
        backref="creator",
        lazy=True,
        foreign_keys="RiskPrediction.created_by",
    )

    feedback_conversations = db.relationship(
        "FeedbackConversation",
        backref="owner",
        lazy=True,
        foreign_keys="FeedbackConversation.user_id",
    )

    feedback_messages_sent = db.relationship(
        "FeedbackMessage",
        backref="author",
        lazy=True,
        foreign_keys="FeedbackMessage.sender_user_id",
    )

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    admission_no = db.Column(db.String(50), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(150), nullable=False)

    gender = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    school_name = db.Column(db.String(150), nullable=False)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)

    year_of_study = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    lecturer_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    academic_records = db.relationship(
        "AcademicRecord",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan",
    )
    questionnaire_responses = db.relationship(
        "QuestionnaireResponse",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan",
    )
    predictions = db.relationship(
        "RiskPrediction",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan",
    )
    interventions = db.relationship(
        "InterventionLog",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan",
    )


class AcademicRecord(db.Model):
    __tablename__ = "academic_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    term_name = db.Column(db.String(50), nullable=False)

    assignment_mark = db.Column(db.Float, nullable=True, default=0.0)
    cat_mark = db.Column(db.Float, nullable=False, default=0.0)
    exam_mark = db.Column(db.Float, nullable=False, default=0.0)

    coursework_total = db.Column(db.Float, nullable=False, default=0.0)
    final_mark = db.Column(db.Float, nullable=False, default=0.0)

    attendance_percent = db.Column(db.Float, nullable=False, default=0.0)
    teacher_comment = db.Column(db.Text, nullable=True)

    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    verified_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def compute_totals(self):
        assignment = self.assignment_mark or 0.0
        cat = self.cat_mark or 0.0
        exam = self.exam_mark or 0.0
        self.coursework_total = assignment + cat
        self.final_mark = self.coursework_total + exam


class QuestionnaireResponse(db.Model):
    __tablename__ = "questionnaire_responses"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    attendance_frequency = db.Column(db.String(50), nullable=False)
    coursework_on_time = db.Column(db.String(50), nullable=False)
    main_challenge = db.Column(db.String(100), nullable=False)
    early_warning_helpful = db.Column(db.String(20), nullable=False)
    study_hours_per_week = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class RiskPrediction(db.Model):
    __tablename__ = "risk_predictions"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    academic_record_id = db.Column(db.Integer, db.ForeignKey("academic_records.id"), nullable=False)
    questionnaire_response_id = db.Column(db.Integer, db.ForeignKey("questionnaire_responses.id"), nullable=False)

    predicted_risk = db.Column(db.String(30), nullable=False)
    high_risk_probability = db.Column(db.Float, nullable=False, default=0.0)
    threshold_used = db.Column(db.Float, nullable=False, default=0.55)
    recommendation = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    academic_record = db.relationship("AcademicRecord", backref="predictions")
    questionnaire_response = db.relationship("QuestionnaireResponse", backref="predictions")


class AccountRequest(db.Model):
    __tablename__ = "account_requests"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    phone = db.Column(db.String(50), nullable=True)

    requested_role = db.Column(db.String(30), nullable=False)
    admission_no = db.Column(db.String(50), nullable=True)
    year_of_study = db.Column(db.Integer, nullable=True)
    semester = db.Column(db.String(20), nullable=True)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)

    status = db.Column(db.String(30), nullable=False, default="pending")
    verification_token = db.Column(db.String(255), nullable=True)
    is_email_verified = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class FeedbackConversation(db.Model):
    __tablename__ = "feedback_conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    sender_name = db.Column(db.String(150), nullable=False)
    sender_email = db.Column(db.String(150), nullable=True)

    support_type = db.Column(db.String(100), nullable=False, default="Other")
    subject = db.Column(db.String(200), nullable=False, default="General Support")

    status = db.Column(db.String(30), nullable=False, default="open")
    last_user_message_at = db.Column(db.DateTime, nullable=True)
    last_admin_message_at = db.Column(db.DateTime, nullable=True)
    last_read_by_user_at = db.Column(db.DateTime, nullable=True)
    last_read_by_admin_at = db.Column(db.DateTime, nullable=True)
    last_message_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    messages = db.relationship(
        "FeedbackMessage",
        backref="conversation",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="FeedbackMessage.created_at.asc()",
    )


class FeedbackMessage(db.Model):
    __tablename__ = "feedback_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("feedback_conversations.id"), nullable=False)

    sender_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    sender_name = db.Column(db.String(150), nullable=False)
    sender_email = db.Column(db.String(150), nullable=True)

    sender_role = db.Column(db.String(30), nullable=False, default="guest")
    body = db.Column(db.Text, nullable=False)

    is_admin_reply = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class InterventionLog(db.Model):
    __tablename__ = "intervention_logs"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    note = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="planned")
    follow_up_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    outcome_note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    author = db.relationship("User", foreign_keys=[created_by])


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    target_type = db.Column(db.String(80), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    actor = db.relationship("User", foreign_keys=[actor_user_id])
