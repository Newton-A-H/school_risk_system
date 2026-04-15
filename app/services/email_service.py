import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app, url_for

from .token_service import generate_token


def send_email(subject, recipient, html_body, text_body=None):
    print("=" * 80)
    print("EMAIL DEBUG")
    print("MAIL_ENABLED:", current_app.config.get("MAIL_ENABLED"))
    print("MAIL_SERVER:", current_app.config.get("MAIL_SERVER"))
    print("MAIL_PORT:", current_app.config.get("MAIL_PORT"))
    print("MAIL_USERNAME:", current_app.config.get("MAIL_USERNAME"))
    print("MAIL_DEFAULT_SENDER:", current_app.config.get("MAIL_DEFAULT_SENDER"))
    print("RECIPIENT:", recipient)
    print("=" * 80)

    if not current_app.config.get("MAIL_ENABLED"):
        print("[MAIL DISABLED] Email sending is off.")
        print(text_body or html_body)
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
        msg["To"] = recipient

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP(
            current_app.config["MAIL_SERVER"],
            current_app.config["MAIL_PORT"],
        )

        if current_app.config.get("MAIL_USE_TLS", True):
            server.starttls()

        server.login(
            current_app.config["MAIL_USERNAME"],
            current_app.config["MAIL_PASSWORD"],
        )

        server.sendmail(msg["From"], [recipient], msg.as_string())
        server.quit()

        print("[EMAIL SUCCESS] Email sent successfully.")
        return True

    except Exception as e:
        print("[EMAIL ERROR]", str(e))
        return False


def send_verification_email(account_request):
    token = generate_token(account_request.email, "account-request-verify")
    verify_url = url_for("main.verify_request_email", token=token, _external=True)
    status_url = url_for("main.request_status", token=account_request.verification_token, _external=True)

    subject = "Verify your EduSentinel AI account request"
    text_body = (
        f"Hello {account_request.full_name},\n\n"
        f"Verify your email here:\n{verify_url}\n\n"
        f"You can track your request here:\n{status_url}\n"
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height:1.6;">
      <h2>EduSentinel AI</h2>
      <p>Hello <strong>{account_request.full_name}</strong>,</p>
      <p>Please verify your email address to continue your account request.</p>
      <p>
        <a href="{verify_url}" style="display:inline-block;padding:10px 18px;background:#22c55e;color:#fff;text-decoration:none;border-radius:999px;">
          Verify Email
        </a>
      </p>
      <p>You can track your request status here:</p>
      <p><a href="{status_url}">{status_url}</a></p>
    </div>
    """
    return send_email(subject, account_request.email, html_body, text_body)


def send_temp_password_email(user, temp_password):
    login_url = url_for("auth.login", _external=True)

    subject = "Your EduSentinel AI account is ready"
    text_body = (
        f"Hello {user.full_name},\n\n"
        f"Your account has been approved.\n"
        f"Email: {user.email}\n"
        f"Temporary Password: {temp_password}\n"
        f"Login here: {login_url}\n"
        f"Please change your password after login.\n"
    )
    html_body = f"""
    <div style="font-family: Arial, sans-serif; line-height:1.6;">
      <h2>EduSentinel AI</h2>
      <p>Hello <strong>{user.full_name}</strong>,</p>
      <p>Your account has been approved.</p>
      <p><strong>Email:</strong> {user.email}</p>
      <p><strong>Temporary Password:</strong> {temp_password}</p>
      <p>
        <a href="{login_url}" style="display:inline-block;padding:10px 18px;background:#22c55e;color:#fff;text-decoration:none;border-radius:999px;">
          Login Now
        </a>
      </p>
      <p>Please change your password after login.</p>
    </div>
    """
    return send_email(subject, user.email, html_body, text_body)