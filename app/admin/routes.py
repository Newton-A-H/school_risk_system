import json
import os
import secrets
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import (
    Student,
    User,
    RiskPrediction,
    Department,
    Course,
    AccountRequest,
    FeedbackConversation,
    FeedbackMessage,
)
from ..utils.decorators import role_required
from ..services.email_service import send_verification_email, send_temp_password_email


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

META_FILE = os.path.join("artifacts", "model_meta.json")
IMPORTANCE_FILE = os.path.join("artifacts", "feature_importance.json")


def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def build_risk_counts():
    counts = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    predictions = RiskPrediction.query.all()
    for prediction in predictions:
        if prediction.predicted_risk in counts:
            counts[prediction.predicted_risk] += 1
    return counts


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    analytics = {
        "risk_counts": build_risk_counts(),
        "feature_importance": load_json_file(IMPORTANCE_FILE, {}),
        "model_meta": load_json_file(META_FILE, {}),
    }

    analytics["top_feature_summary"] = sorted(
        analytics["feature_importance"].items(),
        key=lambda item: item[1],
        reverse=True
    )[:3]

    stats = {
        "student_count": Student.query.count(),
        "prediction_count": RiskPrediction.query.count(),
        "lecturer_count": User.query.filter_by(role="lecturer").count(),
        "admin_count": User.query.filter_by(role="admin").count(),
        "student_user_count": User.query.filter_by(role="student").count(),
        "support_open_count": FeedbackConversation.query.filter_by(status="open").count(),
        "support_total_count": FeedbackConversation.query.count(),
    }

    recent_predictions = (
        RiskPrediction.query.order_by(RiskPrediction.created_at.desc()).limit(10).all()
    )

    return render_template(
        "admin/dashboard.html",
        analytics=analytics,
        stats=stats,
        recent_predictions=recent_predictions,
    )


@admin_bp.route("/accounts")
@login_required
@role_required("admin")
def accounts():
    lecturers = User.query.filter_by(role="lecturer").order_by(User.full_name.asc()).all()
    student_users = User.query.filter_by(role="student").order_by(User.full_name.asc()).all()
    requests = AccountRequest.query.order_by(AccountRequest.created_at.desc()).all()

    return render_template(
        "admin/accounts.html",
        lecturers=lecturers,
        student_users=student_users,
        requests=requests,
    )


@admin_bp.route("/lecturers/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_lecturer():
    departments = Department.query.order_by(Department.name.asc()).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department_id = request.form.get("department_id")
        password = request.form.get("password", "").strip()

        if not full_name or not email or not department_id or not password:
            flash("Full name, email, department, and temporary password are required.", "danger")
            return render_template("admin/new_lecturer.html", departments=departments)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("A user with that email already exists.", "danger")
            return render_template("admin/new_lecturer.html", departments=departments)

        user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role="lecturer",
            department_id=int(department_id),
            is_active_account=True,
            is_verified=True,
            verification_token=None,
            must_change_password=True,
        )
        db.session.add(user)
        db.session.commit()

        flash("Lecturer account created successfully.", "success")
        return redirect(url_for("admin.accounts"))

    return render_template("admin/new_lecturer.html", departments=departments)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("Admin accounts cannot be removed here.", "danger")
        return redirect(url_for("admin.accounts"))

    if user.role == "student":
        linked_student = Student.query.filter_by(user_id=user.id).first()
        if linked_student:
            linked_student.user_id = None

    db.session.delete(user)
    db.session.commit()

    flash("User account removed successfully.", "success")
    return redirect(url_for("admin.accounts"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required("admin")
def reset_password(user_id):
    user = User.query.get_or_404(user_id)

    if user.role == "admin":
        flash("Reset admin passwords directly from a secure admin process.", "warning")
        return redirect(url_for("admin.accounts"))

    temp_password = secrets.token_urlsafe(8)
    user.password_hash = generate_password_hash(temp_password)
    user.must_change_password = True
    db.session.commit()

    send_temp_password_email(user, temp_password)

    flash("Password reset successfully. A new temporary password was sent.", "success")
    return redirect(url_for("admin.accounts"))


@admin_bp.route("/departments")
@login_required
@role_required("admin")
def departments():
    items = Department.query.order_by(Department.name.asc()).all()
    return render_template("admin/departments.html", departments=items)


@admin_bp.route("/departments/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_department():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()

        if not name or not code:
            flash("Department name and code are required.", "danger")
            return render_template("admin/new_department.html")

        existing_name = Department.query.filter_by(name=name).first()
        existing_code = Department.query.filter_by(code=code).first()

        if existing_name or existing_code:
            flash("A department with that name or code already exists.", "danger")
            return render_template("admin/new_department.html")

        dept = Department(name=name, code=code)
        db.session.add(dept)
        db.session.commit()

        flash("Department created successfully.", "success")
        return redirect(url_for("admin.departments"))

    return render_template("admin/new_department.html")


@admin_bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_department(department_id):
    department = Department.query.get_or_404(department_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()

        if not name or not code:
            flash("Department name and code are required.", "danger")
            return render_template("admin/edit_department.html", department=department)

        existing_name = Department.query.filter(Department.name == name, Department.id != department.id).first()
        existing_code = Department.query.filter(Department.code == code, Department.id != department.id).first()

        if existing_name or existing_code:
            flash("Another department already uses that name or code.", "danger")
            return render_template("admin/edit_department.html", department=department)

        department.name = name
        department.code = code
        db.session.commit()

        flash("Department updated successfully.", "success")
        return redirect(url_for("admin.departments"))

    return render_template("admin/edit_department.html", department=department)


@admin_bp.route("/departments/<int:department_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_department(department_id):
    department = Department.query.get_or_404(department_id)

    if department.courses or department.students or department.users:
        flash("This department cannot be deleted because it is linked to courses, learners, or users.", "danger")
        return redirect(url_for("admin.departments"))

    db.session.delete(department)
    db.session.commit()

    flash("Department deleted successfully.", "success")
    return redirect(url_for("admin.departments"))


@admin_bp.route("/courses")
@login_required
@role_required("admin")
def courses():
    items = Course.query.order_by(Course.name.asc()).all()
    return render_template("admin/courses.html", courses=items)


@admin_bp.route("/courses/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_course():
    departments = Department.query.order_by(Department.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        department_id = request.form.get("department_id")
        program_level = request.form.get("program_level")

        if not name or not code or not department_id or not program_level:
            flash("All course fields are required.", "danger")
            return render_template("admin/new_course.html", departments=departments)

        existing_code = Course.query.filter_by(code=code).first()
        if existing_code:
            flash("A course with that code already exists.", "danger")
            return render_template("admin/new_course.html", departments=departments)

        course = Course(
            name=name,
            code=code,
            department_id=int(department_id),
            program_level=program_level,
        )

        db.session.add(course)
        db.session.commit()

        flash("Course created successfully.", "success")
        return redirect(url_for("admin.courses"))

    return render_template("admin/new_course.html", departments=departments)


@admin_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    departments = Department.query.order_by(Department.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()
        department_id = request.form.get("department_id")
        program_level = request.form.get("program_level")

        if not name or not code or not department_id or not program_level:
            flash("All course fields are required.", "danger")
            return render_template("admin/edit_course.html", course=course, departments=departments)

        existing_code = Course.query.filter(Course.code == code, Course.id != course.id).first()
        if existing_code:
            flash("Another course already uses that code.", "danger")
            return render_template("admin/edit_course.html", course=course, departments=departments)

        course.name = name
        course.code = code
        course.department_id = int(department_id)
        course.program_level = program_level
        db.session.commit()

        flash("Course updated successfully.", "success")
        return redirect(url_for("admin.courses"))

    return render_template("admin/edit_course.html", course=course, departments=departments)


@admin_bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)

    if course.students or course.account_requests:
        flash("This course cannot be deleted because it is linked to learners or requests.", "danger")
        return redirect(url_for("admin.courses"))

    db.session.delete(course)
    db.session.commit()

    flash("Course deleted successfully.", "success")
    return redirect(url_for("admin.courses"))


@admin_bp.route("/account-requests")
@login_required
@role_required("admin")
def account_requests():
    requests = AccountRequest.query.order_by(AccountRequest.created_at.desc()).all()
    return render_template("admin/account_requests.html", requests=requests)


@admin_bp.route("/account-requests/<int:request_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_account_request(request_id):
    req = AccountRequest.query.get_or_404(request_id)

    if req.status != "pending":
        flash("This request has already been processed.", "warning")
        return redirect(url_for("admin.account_requests"))

    if not req.is_email_verified:
        flash("This request cannot be approved until the email is verified.", "danger")
        return redirect(url_for("admin.account_requests"))

    existing_user = User.query.filter_by(email=req.email).first()
    if existing_user:
        flash("A user with that email already exists.", "danger")
        return redirect(url_for("admin.account_requests"))

    temp_password = secrets.token_urlsafe(8)

    new_user = User(
        full_name=req.full_name,
        email=req.email,
        password_hash=generate_password_hash(temp_password),
        role=req.requested_role,
        department_id=req.department_id if req.requested_role == "lecturer" else None,
        is_active_account=True,
        is_verified=True,
        verification_token=None,
        must_change_password=True,
    )
    db.session.add(new_user)
    db.session.flush()

    if req.requested_role == "student":
        matched_student = None

        if req.admission_no:
            matched_student = Student.query.filter_by(admission_no=req.admission_no).first()

        if not matched_student and req.email:
            matched_student = Student.query.filter_by(email=req.email).first()

        if matched_student:
            matched_student.user_id = new_user.id
            matched_student.email = req.email
            if req.department_id:
                matched_student.department_id = req.department_id
            if req.course_id:
                matched_student.course_id = req.course_id
            if req.year_of_study:
                matched_student.year_of_study = req.year_of_study
            if req.semester:
                matched_student.semester = req.semester
        else:
            learner = Student(
                admission_no=req.admission_no or f"AUTO-{new_user.id}",
                full_name=req.full_name,
                email=req.email,
                phone=req.phone,
                gender=None,
                school_name="Default School",
                department_id=req.department_id,
                course_id=req.course_id,
                year_of_study=req.year_of_study or 1,
                semester=req.semester or "Semester 1",
                user_id=new_user.id,
                lecturer_user_id=None,
            )
            db.session.add(learner)

    req.status = "approved"
    db.session.commit()

    send_temp_password_email(new_user, temp_password)

    flash(f"Account request approved. A {req.requested_role} account was created automatically.", "success")
    return redirect(url_for("admin.account_requests"))


@admin_bp.route("/account-requests/<int:request_id>/reject", methods=["POST"])
@login_required
@role_required("admin")
def reject_account_request(request_id):
    req = AccountRequest.query.get_or_404(request_id)
    req.status = "rejected"
    db.session.commit()
    flash("Account request rejected.", "warning")
    return redirect(url_for("admin.account_requests"))


@admin_bp.route("/account-requests/<int:request_id>/resend-verification", methods=["POST"])
@login_required
@role_required("admin")
def resend_verification(request_id):
    req = AccountRequest.query.get_or_404(request_id)

    if req.is_email_verified:
        flash("This request is already verified.", "info")
        return redirect(url_for("admin.account_requests"))

    send_verification_email(req)
    flash("Verification message has been resent.", "success")
    return redirect(url_for("admin.account_requests"))


@admin_bp.route("/account-requests/<int:request_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_account_request(request_id):
    req = AccountRequest.query.get_or_404(request_id)

    db.session.delete(req)
    db.session.commit()

    flash("Account request deleted successfully.", "success")
    return redirect(url_for("admin.account_requests"))


@admin_bp.route("/feedback")
@login_required
@role_required("admin")
def feedback_messages():
    conversations = FeedbackConversation.query.order_by(FeedbackConversation.last_message_at.desc()).all()
    return render_template("admin/feedback_messages.html", conversations=conversations)


@admin_bp.route("/feedback/<int:conversation_id>")
@login_required
@role_required("admin")
def feedback_conversation_detail(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    return render_template("admin/feedback_conversation.html", conversation=conversation)


@admin_bp.route("/feedback/<int:conversation_id>/reply", methods=["POST"])
@login_required
@role_required("admin")
def reply_feedback(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)

    if conversation.status != "open":
        flash("This conversation is closed. Reopen it first to send a reply.", "warning")
        return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))

    body = request.form.get("body", "").strip()

    if not body:
        flash("Reply message cannot be empty.", "danger")
        return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))

    message = FeedbackMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        sender_name=current_user.full_name,
        sender_email=current_user.email,
        sender_role="admin",
        body=body,
        is_admin_reply=True,
    )

    conversation.status = "open"
    conversation.last_message_at = datetime.utcnow()

    db.session.add(message)
    db.session.commit()

    flash("Reply sent successfully.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/close", methods=["POST"])
@login_required
@role_required("admin")
def close_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    conversation.status = "closed"
    db.session.commit()

    flash("Conversation closed. Users can no longer send messages in this conversation.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/reopen", methods=["POST"])
@login_required
@role_required("admin")
def reopen_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    conversation.status = "open"
    db.session.commit()

    flash("Conversation reopened.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    db.session.delete(conversation)
    db.session.commit()

    flash("Conversation deleted.", "success")
    return redirect(url_for("admin.feedback_messages"))