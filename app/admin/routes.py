import json
import os
import secrets
import csv
from io import StringIO
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import (
    Student,
    User,
    RiskPrediction,
    Department,
    Course,
    Unit,
    AccountRequest,
    FeedbackConversation,
    FeedbackMessage,
    AuditLog,
    InterventionLog,
    AcademicRecord,
    StudentUnitRegistration,
)
from ..utils.decorators import role_required
from ..services.email_service import send_verification_email, send_temp_password_email
from ..services.artifact_store import META_FILE, IMPORTANCE_FILE, HISTORY_FILE
from ..services.academic import get_default_academic_year, normalize_term_type
from ..ml.training import train_and_save_model


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

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
    seen_pairs = set()
    for prediction in predictions:
        pair = (prediction.student_id, prediction.predicted_risk)
        if prediction.predicted_risk in counts and pair not in seen_pairs:
            counts[prediction.predicted_risk] += 1
            seen_pairs.add(pair)
    return counts


def _csv_download(filename, fieldnames, rows):
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _log_audit(action, target_type, target_id=None, detail=None):
    db.session.add(
        AuditLog(
            actor_user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )


def _conversation_unread_for_admin(conversation):
    return bool(
        conversation.last_user_message_at
        and (
            conversation.last_read_by_admin_at is None
            or conversation.last_user_message_at > conversation.last_read_by_admin_at
        )
    )


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
        "intervention_count": InterventionLog.query.count(),
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


@admin_bp.route("/ml", methods=["GET", "POST"])
@login_required
@role_required("admin")
def ml_control_panel():
    if request.method == "POST":
        meta = train_and_save_model()
        _log_audit("model_retrained", "ml_model", detail=meta.get("message"))
        db.session.commit()
        flash(meta.get("message", "Model retraining completed."), "success" if meta.get("ready") else "warning")
        return redirect(url_for("admin.ml_control_panel"))

    meta = load_json_file(META_FILE, {})
    importance = load_json_file(IMPORTANCE_FILE, {})
    history = load_json_file(HISTORY_FILE, [])
    return render_template(
        "admin/ml_control_panel.html",
        model_meta=meta,
        feature_importance=importance,
        model_history=history,
    )


@admin_bp.route("/exports")
@login_required
@role_required("admin")
def export_center():
    dataset = request.args.get("dataset", "").strip().lower()

    if dataset == "learners":
        rows = []
        learners = Student.query.order_by(Student.full_name.asc()).all()
        for learner in learners:
            linked_user = db.session.get(User, learner.user_id) if learner.user_id else None
            lecturer = db.session.get(User, learner.lecturer_user_id) if learner.lecturer_user_id else None
            rows.append(
                {
                    "admission_no": learner.admission_no,
                    "full_name": learner.full_name,
                    "email": learner.email or "",
                    "phone": learner.phone or "",
                    "department": learner.department.name if learner.department else "",
                    "course": learner.course.name if learner.course else "",
                    "year_of_study": learner.year_of_study,
                    "semester": learner.semester,
                    "term_type": learner.term_type,
                    "academic_year": learner.academic_year,
                    "linked_user_email": linked_user.email if linked_user else "",
                    "lecturer_email": lecturer.email if lecturer else "",
                    "created_at": learner.created_at.isoformat() if learner.created_at else "",
                }
            )
        return _csv_download("edusentinel_learners.csv", list(rows[0].keys()) if rows else [
            "admission_no", "full_name", "email", "phone", "department", "course",
            "year_of_study", "semester", "term_type", "academic_year",
            "linked_user_email", "lecturer_email", "created_at"
        ], rows)

    if dataset == "predictions":
        rows = []
        predictions = RiskPrediction.query.order_by(RiskPrediction.created_at.desc()).all()
        for prediction in predictions:
            rows.append(
                {
                    "student": prediction.student.full_name if prediction.student else "",
                    "admission_no": prediction.student.admission_no if prediction.student else "",
                    "risk_level": prediction.predicted_risk,
                    "confidence_percent": round((prediction.high_risk_probability or 0.0) * 100, 2),
                    "threshold_used": prediction.threshold_used,
                    "created_by": prediction.creator.full_name if prediction.creator else "",
                    "created_at": prediction.created_at.isoformat() if prediction.created_at else "",
                }
            )
        return _csv_download("edusentinel_predictions.csv", list(rows[0].keys()) if rows else [
            "student", "admission_no", "risk_level", "confidence_percent", "threshold_used", "created_by", "created_at"
        ], rows)

    if dataset == "support":
        rows = []
        conversations = FeedbackConversation.query.order_by(FeedbackConversation.last_message_at.desc()).all()
        for conversation in conversations:
            rows.append(
                {
                    "sender_name": conversation.sender_name,
                    "sender_email": conversation.sender_email or "",
                    "category": conversation.support_type,
                    "subject": conversation.subject,
                    "status": conversation.status,
                    "message_count": len(conversation.messages),
                    "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else "",
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else "",
                }
            )
        return _csv_download("edusentinel_support.csv", list(rows[0].keys()) if rows else [
            "sender_name", "sender_email", "category", "subject", "status", "message_count", "last_message_at", "created_at"
        ], rows)

    if dataset == "interventions":
        rows = []
        interventions = InterventionLog.query.order_by(InterventionLog.created_at.desc()).all()
        for item in interventions:
            rows.append(
                {
                    "student": item.student.full_name if item.student else "",
                    "admission_no": item.student.admission_no if item.student else "",
                    "title": item.title,
                    "status": item.status,
                    "follow_up_date": item.follow_up_date.isoformat() if item.follow_up_date else "",
                    "created_by": item.author.full_name if item.author else "",
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                    "completed_at": item.completed_at.isoformat() if item.completed_at else "",
                }
            )
        return _csv_download("edusentinel_interventions.csv", list(rows[0].keys()) if rows else [
            "student", "admission_no", "title", "status", "follow_up_date", "created_by", "created_at", "completed_at"
        ], rows)

    if dataset == "audit":
        rows = []
        items = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
        for item in items:
            rows.append(
                {
                    "actor": item.actor.full_name if item.actor else "",
                    "action": item.action,
                    "target_type": item.target_type,
                    "target_id": item.target_id or "",
                    "detail": item.detail or "",
                    "created_at": item.created_at.isoformat() if item.created_at else "",
                }
            )
        return _csv_download("edusentinel_audit.csv", list(rows[0].keys()) if rows else [
            "actor", "action", "target_type", "target_id", "detail", "created_at"
        ], rows)

    export_cards = [
        {
            "slug": "learners",
            "title": "Learner Records",
            "description": "Download admission details, course placement, and account-link information.",
            "count": Student.query.count(),
        },
        {
            "slug": "predictions",
            "title": "Prediction History",
            "description": "Export every saved prediction with its risk level, confidence, and timestamp.",
            "count": RiskPrediction.query.count(),
        },
        {
            "slug": "support",
            "title": "Support Cases",
            "description": "Get a record of support conversations, categories, and current case status.",
            "count": FeedbackConversation.query.count(),
        },
        {
            "slug": "interventions",
            "title": "Intervention Log",
            "description": "Review planned and completed follow-up actions for learners.",
            "count": InterventionLog.query.count(),
        },
        {
            "slug": "audit",
            "title": "Audit Trail",
            "description": "Keep a CSV snapshot of key admin actions and system activity.",
            "count": AuditLog.query.count(),
        },
    ]

    return render_template("admin/export_center.html", export_cards=export_cards)


@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    department_id = request.args.get("department_id", type=int)
    risk_level = request.args.get("risk_level", type=str)
    semester = request.args.get("semester", type=str)
    export = request.args.get("export", type=str)

    student_query = Student.query
    prediction_query = RiskPrediction.query.join(Student, RiskPrediction.student_id == Student.id)
    record_query = AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)

    if department_id:
        student_query = student_query.filter(Student.department_id == department_id)
        prediction_query = prediction_query.filter(Student.department_id == department_id)
        record_query = record_query.filter(Student.department_id == department_id)
    if risk_level:
        prediction_query = prediction_query.filter(RiskPrediction.predicted_risk == risk_level)
    if semester:
        student_query = student_query.filter(Student.semester == semester)
        prediction_query = prediction_query.filter(Student.semester == semester)
        record_query = record_query.filter(Student.semester == semester)

    students = student_query.all()
    predictions = prediction_query.order_by(RiskPrediction.created_at.desc()).all()
    records = record_query.all()
    support_conversations = FeedbackConversation.query.order_by(FeedbackConversation.last_message_at.desc()).all()
    interventions = InterventionLog.query.join(Student, InterventionLog.student_id == Student.id)
    if department_id:
        interventions = interventions.filter(Student.department_id == department_id)
    if semester:
        interventions = interventions.filter(Student.semester == semester)
    interventions = interventions.all()

    unresolved_support = [item for item in support_conversations if item.status == "open"]
    verification_pending = [item for item in records if not item.is_verified]
    risk_summary = {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0}
    department_summary = {}
    intervention_summary = {"planned": 0, "completed": 0}
    course_summary = {}

    for prediction in predictions:
        risk_summary[prediction.predicted_risk] = risk_summary.get(prediction.predicted_risk, 0) + 1
        dept_name = prediction.student.department.name if prediction.student and prediction.student.department else "Unassigned"
        department_summary.setdefault(dept_name, {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0})
        department_summary[dept_name][prediction.predicted_risk] = department_summary[dept_name].get(prediction.predicted_risk, 0) + 1
        course_name = prediction.student.course.name if prediction.student and prediction.student.course else "Unassigned"
        course_summary.setdefault(course_name, {"Low Risk": 0, "Medium Risk": 0, "High Risk": 0})
        course_summary[course_name][prediction.predicted_risk] = course_summary[course_name].get(prediction.predicted_risk, 0) + 1

    for item in interventions:
        intervention_summary[item.status] = intervention_summary.get(item.status, 0) + 1

    if export == "csv":
        csv_rows = ["Report Type,Reference,Value"]
        for label, value in risk_summary.items():
            csv_rows.append(f"School Risk Summary,{label},{value}")
        for dept_name, counts in department_summary.items():
            for label, value in counts.items():
                csv_rows.append(f"Department Risk Summary,{dept_name} - {label},{value}")
        for course_name, counts in course_summary.items():
            for label, value in counts.items():
                csv_rows.append(f"Course Risk Summary,{course_name} - {label},{value}")
        csv_rows.append(f"Verification Compliance,Pending Records,{len(verification_pending)}")
        csv_rows.append(f"Support,Open Conversations,{len(unresolved_support)}")
        for label, value in intervention_summary.items():
            csv_rows.append(f"Interventions,{label},{value}")
        return Response(
            "\n".join(csv_rows),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=edusentinel_reports.csv"},
        )

    return render_template(
        "admin/reports.html",
        departments=Department.query.order_by(Department.name.asc()).all(),
        filters={
            "department_id": department_id,
            "risk_level": risk_level or "",
            "semester": semester or "",
        },
        risk_summary=risk_summary,
        department_summary=department_summary,
        unresolved_support=unresolved_support,
        verification_pending=verification_pending,
        intervention_summary=intervention_summary,
        course_summary=course_summary,
        prediction_count=len(predictions),
        learner_count=len(students),
    )


@admin_bp.route("/audit")
@login_required
@role_required("admin")
def audit_trail():
    items = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_trail.html", items=items)


@admin_bp.route("/imports", methods=["GET", "POST"])
@login_required
@role_required("admin")
def bulk_imports():
    if request.method == "POST":
        import_type = request.form.get("import_type", "").strip()
        upload = request.files.get("csv_file")

        if not upload or not upload.filename:
            flash("Please choose a CSV file to import.", "danger")
            return redirect(url_for("admin.bulk_imports"))

        try:
            raw_text = upload.read().decode("utf-8-sig")
            rows = list(csv.DictReader(StringIO(raw_text)))
        except Exception:
            flash("The uploaded file could not be read as CSV.", "danger")
            return redirect(url_for("admin.bulk_imports"))

        if not rows:
            flash("The CSV file does not contain any data rows.", "warning")
            return redirect(url_for("admin.bulk_imports"))

        if import_type == "learners":
            created = 0
            skipped = 0
            for row in rows:
                admission_no = (row.get("admission_no") or "").strip()
                full_name = (row.get("full_name") or "").strip()
                department_code = (row.get("department_code") or "").strip().upper()
                course_code = (row.get("course_code") or "").strip().upper()
                semester = (row.get("semester") or "").strip()
                term_type = normalize_term_type((row.get("term_type") or "").strip()) or "semester"
                academic_year = (row.get("academic_year") or "").strip() or get_default_academic_year()

                if not admission_no or not full_name or not department_code or not course_code or not semester:
                    skipped += 1
                    continue

                if Student.query.filter_by(admission_no=admission_no).first():
                    skipped += 1
                    continue

                department = Department.query.filter_by(code=department_code).first()
                course = Course.query.filter_by(code=course_code).first()
                try:
                    year_of_study = int((row.get("year_of_study") or "1").strip())
                except ValueError:
                    skipped += 1
                    continue

                if not department or not course:
                    skipped += 1
                    continue

                student = Student(
                    admission_no=admission_no,
                    full_name=full_name,
                    email=(row.get("email") or "").strip().lower() or None,
                    phone=(row.get("phone") or "").strip() or None,
                    gender=(row.get("gender") or "").strip() or None,
                    school_name=(row.get("school_name") or "").strip() or "Default School",
                    department_id=department.id,
                    course_id=course.id,
                    year_of_study=year_of_study,
                    semester=semester,
                    term_type=term_type,
                    academic_year=academic_year,
                    user_id=None,
                    lecturer_user_id=None,
                )
                db.session.add(student)
                created += 1

            _log_audit("bulk_import_learners", "student", detail=f"created={created}; skipped={skipped}")
            db.session.commit()
            flash(f"Learner import completed. Created {created}, skipped {skipped}.", "success" if created else "warning")
            return redirect(url_for("admin.bulk_imports"))

        if import_type == "academic_records":
            created = 0
            skipped = 0
            for row in rows:
                admission_no = (row.get("admission_no") or "").strip()
                term_name = (row.get("term_name") or "").strip()
                if not admission_no or not term_name:
                    skipped += 1
                    continue

                student = Student.query.filter_by(admission_no=admission_no).first()
                if not student:
                    skipped += 1
                    continue

                try:
                    assignment_mark = float((row.get("assignment_mark") or "0").strip())
                    cat_mark = float((row.get("cat_mark") or "0").strip())
                    exam_mark = float((row.get("exam_mark") or "0").strip())
                    attendance_percent = float((row.get("attendance_percent") or "0").strip())
                except ValueError:
                    skipped += 1
                    continue

                record = AcademicRecord(
                    student_id=student.id,
                    term_name=term_name,
                    assignment_mark=assignment_mark,
                    cat_mark=cat_mark,
                    exam_mark=exam_mark,
                    attendance_percent=attendance_percent,
                    teacher_comment=(row.get("teacher_comment") or "").strip() or None,
                    is_verified=((row.get("is_verified") or "").strip().lower() in {"true", "1", "yes"}),
                    verified_by=current_user.id if ((row.get("is_verified") or "").strip().lower() in {"true", "1", "yes"}) else None,
                    verified_at=datetime.utcnow() if ((row.get("is_verified") or "").strip().lower() in {"true", "1", "yes"}) else None,
                )
                record.compute_totals()
                db.session.add(record)
                created += 1

            _log_audit("bulk_import_academic_records", "academic_record", detail=f"created={created}; skipped={skipped}")
            db.session.commit()
            flash(f"Academic record import completed. Created {created}, skipped {skipped}.", "success" if created else "warning")
            return redirect(url_for("admin.bulk_imports"))

        flash("Unknown import type selected.", "danger")
        return redirect(url_for("admin.bulk_imports"))

    return render_template("admin/bulk_imports.html")


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
        departments=Department.query.order_by(Department.name.asc()).all(),
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
        _log_audit("lecturer_created", "user", detail=email)
        db.session.commit()

        flash("Lecturer account created successfully.", "success")
        return redirect(url_for("admin.accounts"))

    return render_template("admin/new_lecturer.html", departments=departments)


@admin_bp.route("/lecturers/<int:user_id>/link-department", methods=["POST"])
@login_required
@role_required("admin")
def link_lecturer_department(user_id):
    lecturer = User.query.get_or_404(user_id)

    if lecturer.role != "lecturer":
        flash("Only lecturer accounts can be linked to departments here.", "danger")
        return redirect(url_for("admin.accounts"))

    department_id = request.form.get("department_id", type=int)
    if not department_id:
        flash("Please choose a department for this lecturer.", "warning")
        return redirect(url_for("admin.accounts"))

    department = Department.query.get(department_id)
    if not department:
        flash("That department was not found.", "danger")
        return redirect(url_for("admin.accounts"))

    lecturer.department_id = department.id
    _log_audit("lecturer_department_linked", "user", lecturer.id, department.code)
    db.session.commit()

    flash(f"{lecturer.full_name} is now linked to {department.name}.", "success")
    return redirect(url_for("admin.accounts"))


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

    _log_audit("user_deleted", "user", user.id, user.email)
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
    _log_audit("password_reset", "user", user.id, user.email)
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
        _log_audit("department_created", "department", detail=code)
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
        _log_audit("department_updated", "department", department.id, code)
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

    _log_audit("department_deleted", "department", department.id, department.code)
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


@admin_bp.route("/courses/<int:course_id>/units", methods=["GET", "POST"])
@login_required
@role_required("admin")
def manage_units(course_id):
    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip().upper()

        if not name or not code:
            flash("Unit name and code are required.", "danger")
            return render_template("admin/manage_units.html", course=course)

        existing_code = Unit.query.filter_by(code=code).first()
        if existing_code:
            flash("A unit with that code already exists.", "danger")
            return render_template("admin/manage_units.html", course=course)

        db.session.add(Unit(course_id=course.id, name=name, code=code))
        _log_audit("unit_created", "unit", detail=code)
        db.session.commit()

        flash("Unit added successfully.", "success")
        return redirect(url_for("admin.manage_units", course_id=course.id))

    return render_template("admin/manage_units.html", course=course)


@admin_bp.route("/units/<int:unit_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_unit(unit_id):
    unit = Unit.query.get_or_404(unit_id)
    course_id = unit.course_id

    if StudentUnitRegistration.query.filter_by(unit_id=unit.id).first():
        flash("This unit cannot be deleted because it already appears in learner registrations.", "danger")
        return redirect(url_for("admin.manage_units", course_id=course_id))

    _log_audit("unit_deleted", "unit", unit.id, unit.code)
    db.session.delete(unit)
    db.session.commit()

    flash("Unit deleted successfully.", "success")
    return redirect(url_for("admin.manage_units", course_id=course_id))


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
        _log_audit("course_created", "course", detail=code)
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
        _log_audit("course_updated", "course", course.id, code)
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

    _log_audit("course_deleted", "course", course.id, course.code)
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
            if req.term_type:
                matched_student.term_type = req.term_type
            if req.academic_year:
                matched_student.academic_year = req.academic_year
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
                term_type=req.term_type or "semester",
                academic_year=req.academic_year or get_default_academic_year(),
                user_id=new_user.id,
                lecturer_user_id=None,
            )
            db.session.add(learner)

    req.status = "approved"
    _log_audit("account_request_approved", "account_request", req.id, req.email)
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
    _log_audit("account_request_rejected", "account_request", req.id, req.email)
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

    _log_audit("account_request_deleted", "account_request", req.id, req.email)
    db.session.delete(req)
    db.session.commit()

    flash("Account request deleted successfully.", "success")
    return redirect(url_for("admin.account_requests"))


@admin_bp.route("/feedback")
@login_required
@role_required("admin")
def feedback_messages():
    conversations = FeedbackConversation.query.order_by(FeedbackConversation.last_message_at.desc()).all()
    return render_template(
        "admin/feedback_messages.html",
        conversations=conversations,
        unread_count=sum(1 for item in conversations if _conversation_unread_for_admin(item)),
    )


@admin_bp.route("/feedback/<int:conversation_id>")
@login_required
@role_required("admin")
def feedback_conversation_detail(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    conversation.last_read_by_admin_at = datetime.utcnow()
    db.session.commit()
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
    conversation.last_admin_message_at = datetime.utcnow()
    conversation.last_read_by_admin_at = datetime.utcnow()

    db.session.add(message)
    _log_audit("support_reply_sent", "feedback_conversation", conversation.id, conversation.subject)
    db.session.commit()

    flash("Reply sent successfully.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/close", methods=["POST"])
@login_required
@role_required("admin")
def close_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    conversation.status = "closed"
    _log_audit("support_conversation_closed", "feedback_conversation", conversation.id, conversation.subject)
    db.session.commit()

    flash("Conversation closed. Users can no longer send messages in this conversation.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/reopen", methods=["POST"])
@login_required
@role_required("admin")
def reopen_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    conversation.status = "open"
    _log_audit("support_conversation_reopened", "feedback_conversation", conversation.id, conversation.subject)
    db.session.commit()

    flash("Conversation reopened.", "success")
    return redirect(url_for("admin.feedback_conversation_detail", conversation_id=conversation.id))


@admin_bp.route("/feedback/<int:conversation_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_feedback_conversation(conversation_id):
    conversation = FeedbackConversation.query.get_or_404(conversation_id)
    _log_audit("support_conversation_deleted", "feedback_conversation", conversation.id, conversation.subject)
    db.session.delete(conversation)
    db.session.commit()

    flash("Conversation deleted.", "success")
    return redirect(url_for("admin.feedback_messages"))
