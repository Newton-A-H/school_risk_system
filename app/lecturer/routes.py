import json
import os
from datetime import datetime

from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Student, AcademicRecord, RiskPrediction, Department
from ..utils.decorators import role_required


lecturer_bp = Blueprint("lecturer", __name__, url_prefix="/lecturer")

META_FILE = os.path.join("artifacts", "model_meta.json")


def load_json_file(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def get_model_meta():
    return load_json_file(
        META_FILE,
        {
            "ready": False,
            "record_count": 0,
            "test_f1_weighted": 0.0,
            "test_balanced_accuracy": 0.0,
            "message": "Model metadata not available yet.",
        },
    )


@lecturer_bp.route("/dashboard")
@login_required
@role_required("lecturer")
def dashboard():
    model_meta = get_model_meta()

    if not current_user.department_id:
        flash("Your lecturer account is not linked to any department yet. Please contact the administrator.", "warning")
        return render_template(
            "lecturer/dashboard.html",
            department=None,
            students=[],
            predictions=[],
            learner_count=0,
            high_risk_count=0,
            medium_risk_count=0,
            pending_verifications=0,
            model_meta=model_meta,
        )

    department = db.session.get(Department, current_user.department_id)

    students = (
        Student.query.filter_by(department_id=current_user.department_id)
        .order_by(Student.full_name.asc())
        .all()
    )

    student_ids = [student.id for student in students]

    predictions = []
    if student_ids:
        predictions = (
            RiskPrediction.query.filter(RiskPrediction.student_id.in_(student_ids))
            .order_by(RiskPrediction.created_at.desc())
            .limit(20)
            .all()
        )

    learner_count = len(students)
    high_risk_count = sum(1 for prediction in predictions if prediction.predicted_risk == "High Risk")
    medium_risk_count = sum(1 for prediction in predictions if prediction.predicted_risk == "Medium Risk")

    pending_verifications = 0
    if student_ids:
        pending_verifications = (
            AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)
            .filter(
                Student.department_id == current_user.department_id,
                AcademicRecord.is_verified == False,
            )
            .count()
        )

    course_risk_rows = []
    if students:
        for student in students:
            latest_prediction = (
                RiskPrediction.query.filter_by(student_id=student.id)
                .order_by(RiskPrediction.created_at.desc())
                .first()
            )
            key = student.course.code if student.course else "N/A"
            existing = next((row for row in course_risk_rows if row["course_code"] == key), None)
            if not existing:
                existing = {
                    "course_code": student.course.code if student.course else "N/A",
                    "course_name": student.course.name if student.course else "Unknown Course",
                    "learners": 0,
                    "high_risk": 0,
                    "medium_risk": 0,
                }
                course_risk_rows.append(existing)

            existing["learners"] += 1
            if latest_prediction and latest_prediction.predicted_risk == "High Risk":
                existing["high_risk"] += 1
            elif latest_prediction and latest_prediction.predicted_risk == "Medium Risk":
                existing["medium_risk"] += 1

    return render_template(
        "lecturer/dashboard.html",
        department=department,
        students=students,
        predictions=predictions,
        learner_count=learner_count,
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        pending_verifications=pending_verifications,
        model_meta=model_meta,
        course_risk_rows=sorted(course_risk_rows, key=lambda item: (-item["high_risk"], item["course_code"])),
    )


@lecturer_bp.route("/academic-records")
@login_required
@role_required("lecturer")
def academic_records():
    if not current_user.department_id:
        flash("Your lecturer account is not linked to any department yet.", "warning")
        return redirect(url_for("lecturer.dashboard"))

    records = (
        AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)
        .filter(Student.department_id == current_user.department_id)
        .order_by(AcademicRecord.created_at.desc())
        .all()
    )

    return render_template("lecturer/academic_records.html", records=records)


@lecturer_bp.route("/academic-records/<int:record_id>/verify", methods=["POST"])
@login_required
@role_required("lecturer")
def verify_record(record_id):
    record = (
        AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)
        .filter(
            AcademicRecord.id == record_id,
            Student.department_id == current_user.department_id,
        )
        .first_or_404()
    )

    record.is_verified = True
    record.verified_by = current_user.id
    record.verified_at = datetime.utcnow()

    db.session.commit()

    flash("Academic record verified successfully.", "success")
    return redirect(url_for("lecturer.academic_records"))
