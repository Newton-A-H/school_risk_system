import secrets

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User
from ..services.email_service import send_email
from ..services.token_service import generate_token, verify_token


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.before_app_request
def enforce_password_change():
    protected_endpoints = {
        "auth.change_password",
        "auth.logout",
        "auth.reset_password",
        "static",
    }

    if current_user.is_authenticated and current_user.must_change_password:
        if request.endpoint not in protected_endpoints:
            return redirect(url_for("auth.change_password"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html")

        if not user.is_active_account:
            flash("This account is inactive. Please contact the administrator.", "warning")
            return render_template("auth/login.html")

        login_user(user)

        if user.must_change_password:
            flash("Please change your password before continuing.", "warning")
            return redirect(url_for("auth.change_password"))

        return _redirect_by_role(user)

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password", "").strip()
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html")

        if not new_password or len(new_password) < 6:
            flash("New password must be at least 6 characters long.", "danger")
            return render_template("auth/change_password.html")

        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
            return render_template("auth/change_password.html")

        current_user.password_hash = generate_password_hash(new_password)
        current_user.must_change_password = False
        db.session.commit()

        flash("Password changed successfully.", "success")
        return _redirect_by_role(current_user)

    return render_template("auth/change_password.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token = generate_token(user.email, "forgot-password")
            reset_link = url_for("auth.reset_password", token=token, _external=True)

            subject = "Reset your EduSentinel AI password"
            text_body = (
                f"Hello {user.full_name},\n\n"
                f"Use this link to reset your password:\n{reset_link}\n\n"
                f"If you did not request this, please ignore this message."
            )
            html_body = f"""
            <div style="font-family: Arial, sans-serif; line-height: 1.6;">
              <h2>EduSentinel AI</h2>
              <p>Hello <strong>{user.full_name}</strong>,</p>
              <p>Use the button below to reset your password.</p>
              <p>
                <a href="{reset_link}" style="display:inline-block;padding:10px 18px;background:#2563eb;color:#fff;text-decoration:none;border-radius:999px;">
                  Reset Password
                </a>
              </p>
              <p>If the button does not work, use this link:</p>
              <p>{reset_link}</p>
            </div>
            """
            send_email(subject, user.email, html_body, text_body)

        flash("If that email exists in the system, a reset link has been sent.", "info")
        return render_template("auth/forgot_password.html")

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_token(token, "forgot-password", max_age=60 * 60 * 24)
    if not email:
        flash("This reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("No matching account was found.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password or len(new_password) < 6:
            flash("New password must be at least 6 characters long.", "danger")
            return render_template("auth/reset_password.html")

        if new_password != confirm_password:
            flash("New password and confirmation do not match.", "danger")
            return render_template("auth/reset_password.html")

        user.password_hash = generate_password_hash(new_password)
        user.must_change_password = False
        db.session.commit()

        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")


def _redirect_by_role(user):
    if user.role == "admin":
        return redirect(url_for("admin.dashboard"))
    if user.role == "lecturer":
        return redirect(url_for("lecturer.dashboard"))
    if user.role == "student":
        return redirect(url_for("student_portal.dashboard"))
    return redirect(url_for("main.home"))