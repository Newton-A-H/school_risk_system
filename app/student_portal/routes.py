from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Student, AcademicRecord, QuestionnaireResponse, RiskPrediction
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