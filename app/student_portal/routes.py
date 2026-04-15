from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Student, AcademicRecord, QuestionnaireResponse, RiskPrediction, InterventionLog
from ..services.advisory import generate_advisory
from ..utils.decorators import role_required


student_portal_bp = Blueprint("student_portal", __name__, url_prefix="/student")


@student_portal_bp.route("/dashboard")
@login_required
@role_required("student")
def dashboard():
    student = Student.query.filter_by(user_id=current_user.id).first()

    if not student and current_user.email:
        student = Student.query.filter_by(email=current_user.email).first()
        if student and student.user_id is None:
            student.user_id = current_user.id
            db.session.commit()

    if not student:
        return render_template(
            "student_portal/dashboard.html",
            student=None,
            record=None,
            response=None,
            prediction=None,
            history=[],
            advisory=None,
            not_linked=True,
        )

    record = (
        AcademicRecord.query.filter_by(student_id=student.id)
        .order_by(AcademicRecord.created_at.desc())
        .first()
    )

    response = (
        QuestionnaireResponse.query.filter_by(student_id=student.id)
        .order_by(QuestionnaireResponse.created_at.desc())
        .first()
    )

    prediction = (
        RiskPrediction.query.filter_by(student_id=student.id)
        .order_by(RiskPrediction.created_at.desc())
        .first()
    )

    history = (
        RiskPrediction.query.filter_by(student_id=student.id)
        .order_by(RiskPrediction.created_at.desc())
        .all()
    )

    advisory = None
    if record and response and prediction:
        advisory = generate_advisory(
            prediction.predicted_risk,
            record,
            response,
        )

    return render_template(
        "student_portal/dashboard.html",
        student=student,
        record=record,
        response=response,
        prediction=prediction,
        history=history,
        advisory=advisory,
        not_linked=False,
    )


def _resolve_student_for_current_user():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student and current_user.email:
        student = Student.query.filter_by(email=current_user.email).first()
        if student and student.user_id is None:
            student.user_id = current_user.id
            db.session.commit()
    return student


@student_portal_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("student")
def profile():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip().lower()
        student.phone = phone or None
        if email:
            student.email = email
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student_portal.profile"))

    return render_template("student_portal/profile.html", student=student)


@student_portal_bp.route("/academic-history")
@login_required
@role_required("student")
def academic_history():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    records = (
        AcademicRecord.query.filter_by(student_id=student.id)
        .order_by(AcademicRecord.created_at.desc())
        .all()
    )
    return render_template("student_portal/academic_history.html", student=student, records=records)


@student_portal_bp.route("/questionnaire-history")
@login_required
@role_required("student")
def questionnaire_history():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    responses = (
        QuestionnaireResponse.query.filter_by(student_id=student.id)
        .order_by(QuestionnaireResponse.created_at.desc())
        .all()
    )
    return render_template("student_portal/questionnaire_history.html", student=student, responses=responses)


@student_portal_bp.route("/prediction-history")
@login_required
@role_required("student")
def prediction_history():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    predictions = (
        RiskPrediction.query.filter_by(student_id=student.id)
        .order_by(RiskPrediction.created_at.desc())
        .all()
    )
    return render_template("student_portal/prediction_history.html", student=student, predictions=predictions)


@student_portal_bp.route("/interventions")
@login_required
@role_required("student")
def interventions():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    items = (
        InterventionLog.query.filter_by(student_id=student.id)
        .order_by(InterventionLog.created_at.desc())
        .all()
    )
    return render_template("student_portal/interventions.html", student=student, interventions=items)


@student_portal_bp.route("/report")
@login_required
@role_required("student")
def report():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    record = (
        AcademicRecord.query.filter_by(student_id=student.id)
        .order_by(AcademicRecord.created_at.desc())
        .first()
    )
    response = (
        QuestionnaireResponse.query.filter_by(student_id=student.id)
        .order_by(QuestionnaireResponse.created_at.desc())
        .first()
    )
    prediction = (
        RiskPrediction.query.filter_by(student_id=student.id)
        .order_by(RiskPrediction.created_at.desc())
        .first()
    )
    interventions = (
        InterventionLog.query.filter_by(student_id=student.id)
        .order_by(InterventionLog.created_at.desc())
        .all()
    )

    advisory = None
    if record and response and prediction:
        advisory = generate_advisory(
            prediction.predicted_risk,
            record,
            response,
        )

    return render_template(
        "student_portal/report.html",
        student=student,
        record=record,
        response=response,
        prediction=prediction,
        interventions=interventions,
        advisory=advisory,
    )
