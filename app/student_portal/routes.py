from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Student, AcademicRecord, QuestionnaireResponse, RiskPrediction, InterventionLog, StudentUnitRegistration
from ..services.advisory import generate_advisory
from ..services.academic import get_default_academic_year, get_term_calendar, get_term_types, normalize_term_type, validate_term_selection
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
    current_units = (
        StudentUnitRegistration.query.filter_by(
            student_id=student.id,
            academic_year=student.academic_year,
            term_type=student.term_type,
            term_name=student.semester,
        )
        .order_by(StudentUnitRegistration.created_at.desc())
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
        current_units=current_units,
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

    current_units = (
        StudentUnitRegistration.query.filter_by(
            student_id=student.id,
            academic_year=student.academic_year,
            term_type=student.term_type,
            term_name=student.semester,
        )
        .all()
    )
    return render_template("student_portal/profile.html", student=student, current_units=current_units)


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


@student_portal_bp.route("/questionnaire/new", methods=["GET", "POST"])
@login_required
@role_required("student")
def add_questionnaire():
    student = _resolve_student_for_current_user()
    if not student:
        flash("Your account is not linked to a learner profile yet.", "warning")
        return redirect(url_for("student_portal.dashboard"))

    if request.method == "POST":
        academic_year = request.form.get("academic_year", "").strip() or student.academic_year or get_default_academic_year()
        term_type = normalize_term_type(request.form.get("term_type", "")) or student.term_type
        term_name = request.form.get("term_name", "").strip()
        attendance_frequency = request.form.get("attendance_frequency", "").strip()
        coursework_on_time = request.form.get("coursework_on_time", "").strip()
        main_challenge = request.form.get("main_challenge", "").strip()
        early_warning_helpful = request.form.get("early_warning_helpful", "").strip()
        study_hours_per_week = request.form.get("study_hours_per_week", "").strip()

        if not validate_term_selection(term_type, term_name):
            flash("Please choose a valid semester or trimester before saving your check-in.", "danger")
            return render_template(
                "student_portal/questionnaire_new.html",
                student=student,
                term_types=get_term_types(),
                term_calendar=get_term_calendar(),
                default_academic_year=get_default_academic_year(),
            )

        if not attendance_frequency or not coursework_on_time or not main_challenge or not early_warning_helpful or not study_hours_per_week:
            flash("Please complete all check-in fields.", "danger")
            return render_template(
                "student_portal/questionnaire_new.html",
                student=student,
                term_types=get_term_types(),
                term_calendar=get_term_calendar(),
                default_academic_year=get_default_academic_year(),
            )

        try:
            study_hours_value = float(study_hours_per_week)
        except ValueError:
            flash("Study hours per week must be a valid number.", "danger")
            return render_template(
                "student_portal/questionnaire_new.html",
                student=student,
                term_types=get_term_types(),
                term_calendar=get_term_calendar(),
                default_academic_year=get_default_academic_year(),
            )

        db.session.add(
            QuestionnaireResponse(
                student_id=student.id,
                term_name=term_name,
                term_type=term_type,
                academic_year=academic_year,
                attendance_frequency=attendance_frequency,
                coursework_on_time=coursework_on_time,
                main_challenge=main_challenge,
                early_warning_helpful=early_warning_helpful,
                study_hours_per_week=study_hours_value,
            )
        )
        db.session.commit()

        flash("Your check-in has been saved.", "success")
        return redirect(url_for("student_portal.questionnaire_history"))

    return render_template(
        "student_portal/questionnaire_new.html",
        student=student,
        term_types=get_term_types(),
        term_calendar=get_term_calendar(),
        default_academic_year=get_default_academic_year(),
    )


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
