import secrets
import json
import os
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_required
from sqlalchemy import text

from ..extensions import db
from ..models import (
    Department,
    Course,
    AccountRequest,
    FeedbackConversation,
    FeedbackMessage,
    AuditLog,
    Student,
    AcademicRecord,
    InterventionLog,
    RiskPrediction,
)
from ..services.email_service import send_verification_email
from ..services.artifact_store import META_FILE
from ..services.academic import get_default_academic_year, get_term_calendar, get_term_types, normalize_term_type
from ..services.token_service import verify_token


main_bp = Blueprint("main", __name__)


SUPPORT_OPTIONS = [
    "Account Access Problem",
    "Password Reset Help",
    "Verification / Approval Delay",
    "Learner Record Issue",
    "Prediction / Risk Result Question",
    "Academic Record Problem",
    "Questionnaire Problem",
    "Technical Bug / System Error",
    "General Inquiry",
    "Other",
]


def _log_audit(action, target_type, target_id=None, detail=None):
    entry = AuditLog(
        actor_user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.session.add(entry)


def _load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return default
    return default


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "lecturer":
            return redirect(url_for("lecturer.dashboard"))
        if current_user.role == "student":
            return redirect(url_for("student_portal.dashboard"))
    return render_template("main/home.html")


@main_bp.route("/health")
@main_bp.route("/healthz")
def health_check():
    database_ok = True
    error_message = None

    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        database_ok = False
        error_message = str(exc)

    status_code = 200 if database_ok else 503
    return (
        jsonify(
            {
                "status": "ok" if database_ok else "degraded",
                "database": "reachable" if database_ok else "unreachable",
                "error": error_message,
            }
        ),
        status_code,
    )


@main_bp.route("/request-account", methods=["GET", "POST"])
def request_account():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        if current_user.role == "lecturer":
            return redirect(url_for("lecturer.dashboard"))
        if current_user.role == "student":
            return redirect(url_for("student_portal.dashboard"))

    departments = Department.query.order_by(Department.name.asc()).all()
    courses = Course.query.order_by(Course.name.asc()).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        requested_role = request.form.get("requested_role", "").strip()
        department_id = request.form.get("department_id")
        course_id = request.form.get("course_id")
        admission_no = request.form.get("admission_no", "").strip()
        year_of_study = request.form.get("year_of_study", "").strip()
        semester = request.form.get("semester", "").strip()
        term_type = normalize_term_type(request.form.get("term_type", ""))
        academic_year = request.form.get("academic_year", "").strip() or get_default_academic_year()

        if not full_name or not email or not requested_role:
            flash("Full name, email, and requested role are required.", "danger")
            return render_template(
                "main/request_account.html",
                departments=departments,
                courses=courses,
                term_types=get_term_types(),
                term_calendar=get_term_calendar(),
                default_academic_year=get_default_academic_year(),
            )

        existing_request = AccountRequest.query.filter_by(email=email).first()
        if existing_request:
            flash("An account request with that email already exists.", "warning")
            return redirect(url_for("main.request_status_by_email", email=email))

        if requested_role == "student":
            if not department_id or not course_id or not admission_no or not year_of_study or not semester or not term_type:
                flash("Student requests must include admission number, department, course, year of study, academic year, and semester or trimester.", "danger")
                return render_template(
                    "main/request_account.html",
                    departments=departments,
                    courses=courses,
                    term_types=get_term_types(),
                    term_calendar=get_term_calendar(),
                    default_academic_year=get_default_academic_year(),
                )

        if requested_role == "lecturer":
            if not department_id:
                flash("Lecturer requests must include a department.", "danger")
                return render_template(
                    "main/request_account.html",
                    departments=departments,
                    courses=courses,
                    term_types=get_term_types(),
                    term_calendar=get_term_calendar(),
                    default_academic_year=get_default_academic_year(),
                )

        status_token = secrets.token_urlsafe(32)

        new_request = AccountRequest(
            full_name=full_name,
            email=email,
            phone=phone or None,
            requested_role=requested_role,
            admission_no=admission_no or None,
            year_of_study=int(year_of_study) if year_of_study else None,
            semester=semester or None,
            term_type=term_type or None,
            academic_year=academic_year if requested_role == "student" else None,
            department_id=int(department_id) if department_id else None,
            course_id=int(course_id) if course_id else None,
            status="pending",
            verification_token=status_token,
            is_email_verified=False,
        )

        db.session.add(new_request)
        _log_audit(
            "account_request_submitted",
            "account_request",
            detail=f"{requested_role}:{email}",
        )
        db.session.commit()

        send_verification_email(new_request)

        flash("Your request has been submitted. Please verify your email before admin approval.", "success")
        return redirect(url_for("main.request_status_by_email", email=new_request.email))

    return render_template(
        "main/request_account.html",
        departments=departments,
        courses=courses,
        term_types=get_term_types(),
        term_calendar=get_term_calendar(),
        default_academic_year=get_default_academic_year(),
    )


@main_bp.route("/verify-request/<token>")
def verify_request_email(token):
    email = verify_token(token, "account-request-verify", max_age=60 * 60 * 24 * 2)
    if not email:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for("main.home"))

    req = AccountRequest.query.filter_by(email=email).first()
    if not req:
        flash("No matching account request was found.", "danger")
        return redirect(url_for("main.home"))

    req.is_email_verified = True
    _log_audit("account_request_verified", "account_request", req.id, req.email)
    db.session.commit()

    flash("Email verified successfully. Your request is now awaiting administrator approval.", "success")
    return redirect(url_for("main.request_status_by_email", email=req.email))


@main_bp.route("/request-status", methods=["GET", "POST"])
def request_status_lookup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email:
            flash("Please enter the email used for the request.", "danger")
            return render_template("main/request_status_lookup.html")

        req = AccountRequest.query.filter_by(email=email).first()
        if not req:
            flash("No account request was found for that email.", "warning")
            return render_template("main/request_status_lookup.html")

        return redirect(url_for("main.request_status_by_email", email=req.email))

    return render_template("main/request_status_lookup.html")


@main_bp.route("/request-status/email/<path:email>")
def request_status_by_email(email):
    req = AccountRequest.query.filter_by(email=email.strip().lower()).first_or_404()
    return render_template("main/request_status.html", account_request=req)


@main_bp.route("/request-status/token/<token>")
def request_status(token):
    req = AccountRequest.query.filter_by(verification_token=token).first_or_404()
    return render_template("main/request_status.html", account_request=req)


@main_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification_public():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your email address.", "danger")
            return render_template("main/resend_verification.html")

        req = AccountRequest.query.filter_by(email=email).first()

        if not req:
            flash("No account request was found for that email.", "warning")
            return render_template("main/resend_verification.html")

        if req.is_email_verified:
            flash("That email is already verified. Your request can now be reviewed by the administrator.", "info")
            return redirect(url_for("main.request_status_by_email", email=req.email))

        send_verification_email(req)
        flash("Verification email has been resent. Please check your inbox.", "success")
        return redirect(url_for("main.request_status_by_email", email=req.email))

    return render_template("main/resend_verification.html")


@main_bp.route("/support", methods=["POST"])
def submit_feedback():
    sender_name = request.form.get("sender_name", "").strip()
    sender_email = request.form.get("sender_email", "").strip().lower()
    support_type = request.form.get("support_type", "").strip()
    other_subject = request.form.get("other_subject", "").strip()
    body = request.form.get("message", "").strip()

    if not sender_name:
        sender_name = current_user.full_name if current_user.is_authenticated else "Anonymous User"

    if not sender_email and current_user.is_authenticated:
        sender_email = current_user.email

    if not support_type:
        support_type = "General Inquiry"

    if support_type == "Other":
        subject = other_subject or "Other Support Request"
    else:
        subject = support_type

    if not body:
        flash("Please type a message before sending support.", "danger")
        return redirect(request.referrer or url_for("main.home"))

    conversation = None

    if current_user.is_authenticated:
        conversation = (
            FeedbackConversation.query.filter_by(
                user_id=current_user.id,
                support_type=support_type,
                subject=subject,
                status="open",
            )
            .order_by(FeedbackConversation.last_message_at.desc())
            .first()
        )

    if not conversation and sender_email:
        conversation = (
            FeedbackConversation.query.filter_by(
                sender_email=sender_email,
                support_type=support_type,
                subject=subject,
                status="open",
            )
            .order_by(FeedbackConversation.last_message_at.desc())
            .first()
        )

    if not conversation:
        conversation = FeedbackConversation(
            user_id=current_user.id if current_user.is_authenticated else None,
            sender_name=sender_name,
            sender_email=sender_email or None,
            support_type=support_type,
            subject=subject,
            status="open",
            last_user_message_at=datetime.utcnow(),
            last_read_by_user_at=datetime.utcnow() if current_user.is_authenticated else None,
            last_message_at=datetime.utcnow(),
        )
        db.session.add(conversation)
        db.session.flush()
    else:
        conversation.status = "open"
        conversation.last_user_message_at = datetime.utcnow()
        if current_user.is_authenticated:
            conversation.last_read_by_user_at = datetime.utcnow()

    message = FeedbackMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id if current_user.is_authenticated else None,
        sender_name=sender_name,
        sender_email=sender_email or None,
        sender_role=current_user.role if current_user.is_authenticated else "guest",
        body=body,
        is_admin_reply=False,
    )

    conversation.last_message_at = datetime.utcnow()
    if current_user.is_authenticated:
        conversation.last_read_by_user_at = datetime.utcnow()
    db.session.add(message)
    _log_audit(
        "support_message_created",
        "feedback_conversation",
        conversation.id,
        f"{support_type}:{subject}",
    )
    db.session.commit()

    flash("Your support message has been sent successfully.", "success")
    return redirect(url_for("main.my_support_conversation", conversation_id=conversation.id))


@main_bp.route("/my-support")
@login_required
def my_support():
    conversations = (
        FeedbackConversation.query.filter_by(user_id=current_user.id)
        .order_by(FeedbackConversation.last_message_at.desc())
        .all()
    )
    now = datetime.utcnow()
    for conversation in conversations:
        conversation.last_read_by_user_at = now
    if conversations:
        db.session.commit()
    return render_template(
        "main/my_support.html",
        conversations=conversations,
        support_options=SUPPORT_OPTIONS,
    )


@main_bp.route("/my-support/<int:conversation_id>")
@login_required
def my_support_conversation(conversation_id):
    conversation = FeedbackConversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id,
    ).first_or_404()
    conversation.last_read_by_user_at = datetime.utcnow()
    db.session.commit()

    return render_template(
        "main/my_support_conversation.html",
        conversation=conversation,
        support_options=SUPPORT_OPTIONS,
    )


@main_bp.route("/my-support/<int:conversation_id>/reply", methods=["POST"])
@login_required
def reply_support_conversation(conversation_id):
    conversation = FeedbackConversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id,
    ).first_or_404()

    if conversation.status != "open":
        flash("This conversation has been closed by the admin and can no longer receive new messages.", "warning")
        return redirect(url_for("main.my_support_conversation", conversation_id=conversation.id))

    body = request.form.get("body", "").strip()
    if not body:
        flash("Your reply cannot be empty.", "danger")
        return redirect(url_for("main.my_support_conversation", conversation_id=conversation.id))

    message = FeedbackMessage(
        conversation_id=conversation.id,
        sender_user_id=current_user.id,
        sender_name=current_user.full_name,
        sender_email=current_user.email,
        sender_role=current_user.role,
        body=body,
        is_admin_reply=False,
    )

    conversation.last_message_at = datetime.utcnow()
    conversation.last_user_message_at = datetime.utcnow()
    conversation.last_read_by_user_at = datetime.utcnow()
    db.session.add(message)
    _log_audit(
        "support_message_replied",
        "feedback_conversation",
        conversation.id,
        conversation.subject,
    )
    db.session.commit()

    flash("Your reply has been sent.", "success")
    return redirect(url_for("main.my_support_conversation", conversation_id=conversation.id))


@main_bp.route("/notifications")
@login_required
def notifications():
    items = []

    if current_user.role == "admin":
        pending_requests = AccountRequest.query.filter_by(status="pending").order_by(AccountRequest.created_at.desc()).limit(10).all()
        open_support = FeedbackConversation.query.filter_by(status="open").order_by(FeedbackConversation.last_message_at.desc()).limit(10).all()
        model_meta = _load_json_file(META_FILE, {"ready": False, "message": "Model metadata not available."})

        for req in pending_requests:
            items.append(
                {
                    "title": "Pending account request",
                    "body": f"{req.full_name} requested {req.requested_role} access.",
                    "link": url_for("admin.account_requests"),
                    "timestamp": req.created_at,
                    "badge": "text-bg-warning",
                }
            )
        for conversation in open_support:
            items.append(
                {
                    "title": "Open support conversation",
                    "body": f"{conversation.subject} from {conversation.sender_name} is still open.",
                    "link": url_for("admin.feedback_conversation_detail", conversation_id=conversation.id),
                    "timestamp": conversation.last_message_at,
                    "badge": "text-bg-danger" if conversation.last_user_message_at else "text-bg-secondary",
                }
            )
        if not model_meta.get("ready"):
            items.append(
                {
                    "title": "Model not ready",
                    "body": model_meta.get("message", "Train the model from the ML control panel."),
                    "link": url_for("admin.ml_control_panel"),
                    "timestamp": None,
                    "badge": "text-bg-dark",
                }
            )

    elif current_user.role == "lecturer":
        pending_records = (
            AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)
            .filter(
                Student.department_id == current_user.department_id,
                AcademicRecord.is_verified == False,
            )
            .order_by(AcademicRecord.created_at.desc())
            .limit(10)
            .all()
        ) if current_user.department_id else []

        high_risk_predictions = (
            RiskPrediction.query.join(Student, RiskPrediction.student_id == Student.id)
            .filter(
                Student.department_id == current_user.department_id,
                RiskPrediction.predicted_risk == "High Risk",
            )
            .order_by(RiskPrediction.created_at.desc())
            .limit(10)
            .all()
        ) if current_user.department_id else []

        user_conversations = (
            FeedbackConversation.query.filter_by(user_id=current_user.id)
            .order_by(FeedbackConversation.last_message_at.desc())
            .limit(10)
            .all()
        )

        for record in pending_records:
            items.append(
                {
                    "title": "Academic record awaiting verification",
                    "body": f"{record.student.full_name} | {record.term_name} is pending your review.",
                    "link": url_for("lecturer.academic_records"),
                    "timestamp": record.created_at,
                    "badge": "text-bg-warning",
                }
            )
        for prediction in high_risk_predictions:
            items.append(
                {
                    "title": "High-risk learner alert",
                    "body": f"{prediction.student.full_name} was marked High Risk.",
                    "link": url_for("students.detail", student_id=prediction.student_id),
                    "timestamp": prediction.created_at,
                    "badge": "text-bg-danger",
                }
            )
        for conversation in user_conversations:
            if conversation.last_admin_message_at and (
                conversation.last_read_by_user_at is None
                or conversation.last_admin_message_at > conversation.last_read_by_user_at
            ):
                items.append(
                    {
                        "title": "Unread support reply",
                        "body": f"Admin replied to your support request: {conversation.subject}.",
                        "link": url_for("main.my_support_conversation", conversation_id=conversation.id),
                        "timestamp": conversation.last_admin_message_at,
                        "badge": "text-bg-primary",
                    }
                )

    elif current_user.role == "student":
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student and current_user.email:
            student = Student.query.filter_by(email=current_user.email).first()

        user_conversations = (
            FeedbackConversation.query.filter_by(user_id=current_user.id)
            .order_by(FeedbackConversation.last_message_at.desc())
            .limit(10)
            .all()
        )
        for conversation in user_conversations:
            if conversation.last_admin_message_at and (
                conversation.last_read_by_user_at is None
                or conversation.last_admin_message_at > conversation.last_read_by_user_at
            ):
                items.append(
                    {
                        "title": "Unread support reply",
                        "body": f"Admin replied to your support request: {conversation.subject}.",
                        "link": url_for("main.my_support_conversation", conversation_id=conversation.id),
                        "timestamp": conversation.last_admin_message_at,
                        "badge": "text-bg-primary",
                    }
                )

        if student:
            planned_interventions = (
                InterventionLog.query.filter_by(student_id=student.id, status="planned")
                .order_by(InterventionLog.follow_up_date.asc(), InterventionLog.created_at.desc())
                .limit(10)
                .all()
            )
            predictions = (
                RiskPrediction.query.filter_by(student_id=student.id)
                .order_by(RiskPrediction.created_at.desc())
                .limit(5)
                .all()
            )

            for intervention in planned_interventions:
                follow_up_label = intervention.follow_up_date.strftime("%d %b %Y") if intervention.follow_up_date else "No follow-up date"
                items.append(
                    {
                        "title": "Pending intervention task",
                        "body": f"{intervention.title} | Follow-up: {follow_up_label}.",
                        "link": url_for("student_portal.interventions"),
                        "timestamp": intervention.created_at,
                        "badge": "text-bg-warning",
                    }
                )
            for prediction in predictions:
                if prediction.predicted_risk in {"High Risk", "Medium Risk"}:
                    items.append(
                        {
                            "title": "Risk update",
                            "body": f"Your latest prediction is {prediction.predicted_risk}. Review the recommendation and next steps.",
                            "link": url_for("student_portal.dashboard"),
                            "timestamp": prediction.created_at,
                            "badge": "text-bg-danger" if prediction.predicted_risk == "High Risk" else "text-bg-warning",
                        }
                    )

    dated_items = [item for item in items if item["timestamp"] is not None]
    undated_items = [item for item in items if item["timestamp"] is None]
    dated_items.sort(key=lambda item: item["timestamp"], reverse=True)

    return render_template(
        "main/notifications.html",
        items=dated_items + undated_items,
    )
