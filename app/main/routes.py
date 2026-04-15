import secrets
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (
    Department,
    Course,
    AccountRequest,
    FeedbackConversation,
    FeedbackMessage,
)
from ..services.email_service import send_verification_email
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

        if not full_name or not email or not requested_role:
            flash("Full name, email, and requested role are required.", "danger")
            return render_template("main/request_account.html", departments=departments, courses=courses)

        existing_request = AccountRequest.query.filter_by(email=email).first()
        if existing_request:
            flash("An account request with that email already exists.", "warning")
            return redirect(url_for("main.request_status_by_email", email=email))

        if requested_role == "student":
            if not department_id or not course_id or not admission_no or not year_of_study or not semester:
                flash("Student requests must include admission number, department, course, year of study, and semester.", "danger")
                return render_template("main/request_account.html", departments=departments, courses=courses)

        if requested_role == "lecturer":
            if not department_id:
                flash("Lecturer requests must include a department.", "danger")
                return render_template("main/request_account.html", departments=departments, courses=courses)

        status_token = secrets.token_urlsafe(32)

        new_request = AccountRequest(
            full_name=full_name,
            email=email,
            phone=phone or None,
            requested_role=requested_role,
            admission_no=admission_no or None,
            year_of_study=int(year_of_study) if year_of_study else None,
            semester=semester or None,
            department_id=int(department_id) if department_id else None,
            course_id=int(course_id) if course_id else None,
            status="pending",
            verification_token=status_token,
            is_email_verified=False,
        )

        db.session.add(new_request)
        db.session.commit()

        send_verification_email(new_request)

        flash("Your request has been submitted. Please verify your email before admin approval.", "success")
        return redirect(url_for("main.request_status_by_email", email=new_request.email))

    return render_template("main/request_account.html", departments=departments, courses=courses)


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
            last_message_at=datetime.utcnow(),
        )
        db.session.add(conversation)
        db.session.flush()

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
    db.session.add(message)
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
    db.session.add(message)
    db.session.commit()

    flash("Your reply has been sent.", "success")
    return redirect(url_for("main.my_support_conversation", conversation_id=conversation.id))