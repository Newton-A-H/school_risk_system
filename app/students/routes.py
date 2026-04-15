from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import (
    Student,
    Department,
    Course,
    AcademicRecord,
    QuestionnaireResponse,
    RiskPrediction,
    User,
)
from ..utils.decorators import role_required
from ..services.advisory import generate_advisory
from ..ml.predictor import predict_record


students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.route("/")
@login_required
@role_required("admin", "lecturer")
def index():
    if current_user.role == "lecturer":
        if current_user.department_id:
            students = (
                Student.query.filter_by(department_id=current_user.department_id)
                .order_by(Student.created_at.desc())
                .all()
            )
        else:
            students = []
    else:
        students = Student.query.order_by(Student.created_at.desc()).all()

    return render_template("students/index.html", students=students)


@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def create():
    departments = Department.query.order_by(Department.name.asc()).all()
    courses = Course.query.order_by(Course.name.asc()).all()

    if request.method == "POST":
        admission_no = request.form.get("admission_no", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        course_id = request.form.get("course_id")
        year_of_study = request.form.get("year_of_study")
        semester = request.form.get("semester", "").strip()
        temporary_password = request.form.get("temporary_password", "").strip()

        if not admission_no or not full_name or not email or not department_id or not course_id or not year_of_study or not semester or not temporary_password:
            flash("Please fill in all required learner and account fields.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses)

        existing_student = Student.query.filter_by(admission_no=admission_no).first()
        if existing_student:
            flash("A learner with that admission number already exists.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("A user account with that email already exists.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses)

        user = User(
            full_name=full_name,
            email=email,
            role="student",
            is_active_account=True,
            is_verified=True,
            verification_token=None,
            must_change_password=True,
        )
        user.set_password(temporary_password)

        db.session.add(user)
        db.session.flush()

        student = Student(
            admission_no=admission_no,
            full_name=full_name,
            email=email,
            phone=phone if phone else None,
            gender=None,
            school_name="Default School",
            department_id=int(department_id),
            course_id=int(course_id),
            year_of_study=int(year_of_study),
            semester=semester,
            user_id=user.id,
            lecturer_user_id=None,
        )

        db.session.add(student)
        db.session.commit()

        flash("Learner record and student account created successfully.", "success")
        return redirect(url_for("students.index"))

    return render_template("students/new.html", departments=departments, courses=courses)


@students_bp.route("/<int:student_id>")
@login_required
@role_required("admin", "lecturer")
def detail(student_id):
    query = Student.query

    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)

    student = query.filter_by(id=student_id).first_or_404()

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

    advisory = None
    if record and response and prediction:
        advisory = generate_advisory(
            prediction.predicted_risk,
            record,
            response,
        )

    return render_template(
        "students/detail.html",
        student=student,
        record=record,
        response=response,
        prediction=prediction,
        advisory=advisory,
    )


@students_bp.route("/<int:student_id>/academic/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def add_academic_record(student_id):
    query = Student.query
    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)

    student = query.filter_by(id=student_id).first_or_404()

    if request.method == "POST":
        term_name = request.form.get("term_name", "").strip()
        assignment_mark = request.form.get("assignment_mark", "").strip()
        cat_mark = request.form.get("cat_mark", "").strip()
        exam_mark = request.form.get("exam_mark", "").strip()
        attendance_percent = request.form.get("attendance_percent", "").strip()
        teacher_comment = request.form.get("teacher_comment", "").strip()

        if not term_name or not cat_mark or not exam_mark or not attendance_percent:
            flash("Please fill in all required academic fields.", "danger")
            return render_template("students/academic_form.html", student=student)

        try:
            assignment_value = float(assignment_mark) if assignment_mark else 0.0
            cat_value = float(cat_mark)
            exam_value = float(exam_mark)
            attendance_value = float(attendance_percent)
        except ValueError:
            flash("Marks and attendance must be valid numbers.", "danger")
            return render_template("students/academic_form.html", student=student)

        record = AcademicRecord(
            student_id=student.id,
            term_name=term_name,
            assignment_mark=assignment_value,
            cat_mark=cat_value,
            exam_mark=exam_value,
            attendance_percent=attendance_value,
            teacher_comment=teacher_comment or None,
            is_verified=False,
        )
        record.compute_totals()

        db.session.add(record)
        db.session.commit()

        flash("Academic record saved successfully.", "success")
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template("students/academic_form.html", student=student)


@students_bp.route("/<int:student_id>/questionnaire/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def add_questionnaire(student_id):
    query = Student.query

    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)

    student = query.filter_by(id=student_id).first_or_404()

    if request.method == "POST":
        attendance_frequency = request.form.get("attendance_frequency", "").strip()
        coursework_on_time = request.form.get("coursework_on_time", "").strip()
        main_challenge = request.form.get("main_challenge", "").strip()
        early_warning_helpful = request.form.get("early_warning_helpful", "").strip()
        study_hours_per_week = request.form.get("study_hours_per_week", "").strip()

        if not attendance_frequency or not coursework_on_time or not main_challenge or not early_warning_helpful or not study_hours_per_week:
            flash("Please fill in all questionnaire fields.", "danger")
            return render_template("students/questionnaire_form.html", student=student)

        try:
            study_hours_value = float(study_hours_per_week)
        except ValueError:
            flash("Study hours per week must be a valid number.", "danger")
            return render_template("students/questionnaire_form.html", student=student)

        response = QuestionnaireResponse(
            student_id=student.id,
            attendance_frequency=attendance_frequency,
            coursework_on_time=coursework_on_time,
            main_challenge=main_challenge,
            early_warning_helpful=early_warning_helpful,
            study_hours_per_week=study_hours_value,
        )

        db.session.add(response)
        db.session.commit()

        flash("Questionnaire saved successfully.", "success")
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template("students/questionnaire_form.html", student=student)


@students_bp.route("/<int:student_id>/predict", methods=["POST"])
@login_required
@role_required("admin", "lecturer")
def run_prediction(student_id):
    query = Student.query

    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)

    student = query.filter_by(id=student_id).first_or_404()

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

    if not record:
        flash("Please add an academic record before running prediction.", "danger")
        return redirect(url_for("students.detail", student_id=student.id))

    if not response:
        flash("Please add a questionnaire before running prediction.", "danger")
        return redirect(url_for("students.detail", student_id=student.id))

    payload = {
        "marks": record.final_mark,
        "attendance_percent": record.attendance_percent,
        "coursework_mark": record.coursework_total,
        "exam_mark": record.exam_mark,
        "year_of_study": student.year_of_study,
        "attendance_frequency": response.attendance_frequency,
        "coursework_on_time": response.coursework_on_time,
        "main_challenge": response.main_challenge,
        "early_warning_helpful": response.early_warning_helpful,
        "study_hours_per_week": response.study_hours_per_week,
    }

    result = predict_record(payload)
    advisory = generate_advisory(result["risk_level"], record, response)

    prediction = RiskPrediction(
        student_id=student.id,
        academic_record_id=record.id,
        questionnaire_response_id=response.id,
        predicted_risk=result["risk_level"],
        high_risk_probability=result["probabilities"].get("High Risk", 0.0),
        threshold_used=result["threshold"],
        recommendation=advisory["summary"],
        created_by=current_user.id,
    )

    db.session.add(prediction)
    db.session.commit()

    if not result["meta"].get("ready", False):
        flash(
            "Prediction used the fallback starter engine because the full AI model is not trained yet.",
            "warning",
        )
    else:
        flash("Prediction generated successfully.", "success")

    return redirect(url_for("students.detail", student_id=student.id))


@students_bp.route("/<int:student_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "lecturer")
def delete(student_id):
    query = Student.query

    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)

    student = query.filter_by(id=student_id).first_or_404()

    db.session.delete(student)
    db.session.commit()

    flash("Learner record deleted successfully.", "success")
    return redirect(url_for("students.index"))