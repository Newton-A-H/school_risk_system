import csv
from io import StringIO

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import (
    Student,
    Department,
    Course,
    Unit,
    AcademicRecord,
    QuestionnaireResponse,
    RiskPrediction,
    User,
    InterventionLog,
    StudentUnitRegistration,
)
from ..utils.decorators import role_required
from ..services.advisory import generate_advisory
from ..services.academic import (
    MAX_UNITS_PER_TERM,
    TERM_STRUCTURES,
    get_default_academic_year,
    get_term_calendar,
    get_term_choices,
    get_term_types,
    normalize_term_type,
    validate_term_selection,
)
from ..ml.predictor import predict_record


students_bp = Blueprint("students", __name__, url_prefix="/students")


def _student_query_for_current_user():
    query = Student.query.options(
        joinedload(Student.course).joinedload(Course.units),
        joinedload(Student.unit_registrations).joinedload(StudentUnitRegistration.unit),
    )
    if current_user.role == "lecturer":
        query = query.filter_by(department_id=current_user.department_id)
    return query


def _build_registration_snapshot(student):
    registrations = {}
    for item in student.unit_registrations:
        key = (item.academic_year, item.term_type, item.term_name)
        registrations.setdefault(
            key,
            {
                "academic_year": item.academic_year,
                "term_type": item.term_type,
                "term_name": item.term_name,
                "units": [],
            },
        )
        registrations[key]["units"].append(item.unit)

    snapshots = list(registrations.values())
    snapshots.sort(key=lambda item: (item["academic_year"], item["term_name"]), reverse=True)
    return snapshots


def _current_registration_ids(student):
    return [
        item.unit_id
        for item in student.unit_registrations
        if item.academic_year == student.academic_year
        and item.term_type == student.term_type
        and item.term_name == student.semester
    ]


def _parse_whole_number(value, label):
    raw = (value or "").strip()
    if not raw:
        raise ValueError(f"{label} is required.")
    if "." in raw:
        raise ValueError(f"{label} must be a whole number.")
    return int(raw)


def _extract_registration_form(request_obj):
    academic_year = request_obj.form.get("academic_year", "").strip() or get_default_academic_year()
    term_type = normalize_term_type(request_obj.form.get("term_type", ""))
    term_name = request_obj.form.get("semester", "").strip()
    unit_ids = [item for item in request_obj.form.getlist("unit_ids") if item.strip()]
    return academic_year, term_type, term_name, unit_ids


def _validate_registration(course, term_type, term_name, unit_ids):
    if not validate_term_selection(term_type, term_name):
        return "Please choose a valid semester or trimester option."

    if len(unit_ids) > MAX_UNITS_PER_TERM:
        return f"A learner can only register up to {MAX_UNITS_PER_TERM} units in one academic period."

    available_units = {str(unit.id): unit for unit in course.units}
    if unit_ids and any(unit_id not in available_units for unit_id in unit_ids):
        return "One or more selected units do not belong to the chosen course."

    return None


def _replace_registrations_for_term(student, academic_year, term_type, term_name, unit_ids):
    existing = StudentUnitRegistration.query.filter_by(
        student_id=student.id,
        academic_year=academic_year,
        term_type=term_type,
        term_name=term_name,
    ).all()
    for item in existing:
        db.session.delete(item)

    for unit_id in unit_ids:
        db.session.add(
            StudentUnitRegistration(
                student_id=student.id,
                unit_id=int(unit_id),
                academic_year=academic_year,
                term_type=term_type,
                term_name=term_name,
            )
        )


def _term_context():
    return {
        "term_types": get_term_types(),
        "term_calendar": get_term_calendar(),
        "term_choices": {key: value["terms"] for key, value in TERM_STRUCTURES.items()},
        "default_academic_year": get_default_academic_year(),
        "max_units_per_term": MAX_UNITS_PER_TERM,
    }


@students_bp.route("/")
@login_required
@role_required("admin", "lecturer")
def index():
    search = request.args.get("search", "").strip()
    course_id = request.args.get("course_id", type=int)
    year = request.args.get("year", type=int)
    semester = request.args.get("semester", "").strip()
    risk_level = request.args.get("risk_level", "").strip()
    export = request.args.get("export", "").strip().lower()

    if current_user.role == "lecturer":
        if not current_user.department_id:
            students = []
            courses = []
            return render_template(
                "students/index.html",
                students=students,
                courses=courses,
                filters={"search": search, "course_id": course_id, "year": year, "semester": semester, "risk_level": risk_level},
            )
        query = Student.query.filter_by(department_id=current_user.department_id)
        courses = Course.query.filter_by(department_id=current_user.department_id).order_by(Course.name.asc()).all()
    else:
        query = Student.query
        courses = Course.query.order_by(Course.name.asc()).all()

    if search:
        like_value = f"%{search}%"
        query = query.filter(
            (Student.full_name.ilike(like_value)) |
            (Student.admission_no.ilike(like_value))
        )
    if course_id:
        query = query.filter(Student.course_id == course_id)
    if year:
        query = query.filter(Student.year_of_study == year)
    if semester:
        query = query.filter(Student.semester == semester)
    if risk_level:
        query = query.join(RiskPrediction, RiskPrediction.student_id == Student.id).filter(RiskPrediction.predicted_risk == risk_level).distinct()

    students = query.order_by(Student.created_at.desc()).all()

    if export == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Admission No", "Full Name", "Department", "Course", "Year", "Semester"])
        for student in students:
            writer.writerow([
                student.admission_no,
                student.full_name,
                student.department.name if student.department else "",
                student.course.name if student.course else "",
                student.year_of_study,
                f"{student.academic_year} | {student.semester}",
            ])
        filename = "department_learners.csv" if current_user.role == "lecturer" else "all_learners.csv"
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return render_template(
        "students/index.html",
        students=students,
        courses=courses,
        filters={"search": search, "course_id": course_id, "year": year, "semester": semester, "risk_level": risk_level},
    )


@students_bp.route("/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def create():
    departments = Department.query.order_by(Department.name.asc()).all()
    courses = Course.query.options(joinedload(Course.units)).order_by(Course.name.asc()).all()

    if request.method == "POST":
        admission_no = request.form.get("admission_no", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id")
        course_id = request.form.get("course_id")
        year_of_study = request.form.get("year_of_study")
        academic_year, term_type, semester, unit_ids = _extract_registration_form(request)
        temporary_password = request.form.get("temporary_password", "").strip()

        if not admission_no or not full_name or not email or not department_id or not course_id or not year_of_study or not semester or not temporary_password:
            flash("Please fill in all required learner and account fields.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses, **_term_context())

        existing_student = Student.query.filter_by(admission_no=admission_no).first()
        if existing_student:
            flash("A learner with that admission number already exists.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("A user account with that email already exists.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses, **_term_context())

        selected_course = Course.query.options(joinedload(Course.units)).filter_by(id=int(course_id)).first()
        if not selected_course:
            flash("The selected course could not be found.", "danger")
            return render_template("students/new.html", departments=departments, courses=courses, **_term_context())

        registration_error = _validate_registration(selected_course, term_type, semester, unit_ids)
        if registration_error:
            flash(registration_error, "danger")
            return render_template("students/new.html", departments=departments, courses=courses, **_term_context())

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
            term_type=term_type,
            academic_year=academic_year,
            user_id=user.id,
            lecturer_user_id=None,
        )

        db.session.add(student)
        db.session.flush()
        _replace_registrations_for_term(student, academic_year, term_type, semester, unit_ids)
        db.session.commit()

        flash("Learner record and student account created successfully.", "success")
        return redirect(url_for("students.index"))

    return render_template("students/new.html", departments=departments, courses=courses, **_term_context())


@students_bp.route("/<int:student_id>")
@login_required
@role_required("admin", "lecturer")
def detail(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()

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

    interventions = (
        InterventionLog.query.filter_by(student_id=student.id)
        .order_by(InterventionLog.created_at.desc())
        .all()
    )
    academic_history = (
        AcademicRecord.query.filter_by(student_id=student.id)
        .order_by(AcademicRecord.created_at.desc())
        .all()
    )
    questionnaire_history = (
        QuestionnaireResponse.query.filter_by(student_id=student.id)
        .order_by(QuestionnaireResponse.created_at.desc())
        .all()
    )
    registration_history = _build_registration_snapshot(student)

    return render_template(
        "students/detail.html",
        student=student,
        record=record,
        response=response,
        prediction=prediction,
        advisory=advisory,
        interventions=interventions,
        academic_history=academic_history,
        questionnaire_history=questionnaire_history,
        registration_history=registration_history,
    )


@students_bp.route("/<int:student_id>/academic/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def add_academic_record(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()
    current_units = [
        item.unit
        for item in student.unit_registrations
        if item.academic_year == student.academic_year
        and item.term_type == student.term_type
        and item.term_name == student.semester
    ]
    if not current_units:
        current_units = list(student.course.units)

    if request.method == "POST":
        academic_year = request.form.get("academic_year", "").strip() or student.academic_year or get_default_academic_year()
        term_type = normalize_term_type(request.form.get("term_type", "")) or student.term_type
        term_name = request.form.get("term_name", "").strip()
        unit_id = request.form.get("unit_id", "").strip()
        assignment_mark = request.form.get("assignment_mark", "").strip()
        cat_mark = request.form.get("cat_mark", "").strip()
        exam_mark = request.form.get("exam_mark", "").strip()
        attendance_percent = request.form.get("attendance_percent", "").strip()
        teacher_comment = request.form.get("teacher_comment", "").strip()

        if not validate_term_selection(term_type, term_name):
            flash("Please choose a valid semester or trimester for this record.", "danger")
            return render_template("students/academic_form.html", student=student, current_units=current_units, **_term_context())

        if not unit_id or not term_name or not cat_mark or not exam_mark or not attendance_percent:
            flash("Please fill in all required academic fields.", "danger")
            return render_template("students/academic_form.html", student=student, current_units=current_units, **_term_context())

        selected_unit = next((unit for unit in current_units if str(unit.id) == unit_id), None)
        if not selected_unit:
            flash("Please choose a valid unit for this academic record.", "danger")
            return render_template("students/academic_form.html", student=student, current_units=current_units, **_term_context())

        try:
            assignment_value = _parse_whole_number(assignment_mark, "Assignment mark") if assignment_mark else 0
            cat_value = _parse_whole_number(cat_mark, "CAT mark")
            exam_value = _parse_whole_number(exam_mark, "Exam mark")
            attendance_value = _parse_whole_number(attendance_percent, "Attendance percentage")
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("students/academic_form.html", student=student, current_units=current_units, **_term_context())

        record = AcademicRecord(
            student_id=student.id,
            unit_id=selected_unit.id,
            term_name=term_name,
            term_type=term_type,
            academic_year=academic_year,
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

    return render_template("students/academic_form.html", student=student, current_units=current_units, **_term_context())


@students_bp.route("/<int:student_id>/questionnaire/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def add_questionnaire(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()

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
            flash("Please choose a valid semester or trimester for this check-in.", "danger")
            return render_template("students/questionnaire_form.html", student=student, **_term_context())

        if not attendance_frequency or not coursework_on_time or not main_challenge or not early_warning_helpful or not study_hours_per_week:
            flash("Please fill in all questionnaire fields.", "danger")
            return render_template("students/questionnaire_form.html", student=student, **_term_context())

        try:
            study_hours_value = float(study_hours_per_week)
        except ValueError:
            flash("Study hours per week must be a valid number.", "danger")
            return render_template("students/questionnaire_form.html", student=student, **_term_context())

        response = QuestionnaireResponse(
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

        db.session.add(response)
        db.session.commit()

        flash("Questionnaire saved successfully.", "success")
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template("students/questionnaire_form.html", student=student, **_term_context())


@students_bp.route("/<int:student_id>/predict", methods=["POST"])
@login_required
@role_required("admin", "lecturer")
def run_prediction(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()

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
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()

    db.session.delete(student)
    db.session.commit()

    flash("Learner record deleted successfully.", "success")
    return redirect(url_for("students.index"))


@students_bp.route("/<int:student_id>/interventions/new", methods=["POST"])
@login_required
@role_required("admin", "lecturer")
def add_intervention(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()
    title = request.form.get("title", "").strip()
    note = request.form.get("note", "").strip()
    follow_up_date = request.form.get("follow_up_date", "").strip()

    if not title or not note:
        flash("Intervention title and note are required.", "danger")
        return redirect(url_for("students.detail", student_id=student.id))

    follow_up_value = None
    if follow_up_date:
        from datetime import datetime
        try:
            follow_up_value = datetime.strptime(follow_up_date, "%Y-%m-%d")
        except ValueError:
            flash("Follow-up date must be valid.", "danger")
            return redirect(url_for("students.detail", student_id=student.id))

    item = InterventionLog(
        student_id=student.id,
        created_by=current_user.id,
        title=title,
        note=note,
        status="planned",
        follow_up_date=follow_up_value,
    )
    db.session.add(item)
    db.session.commit()

    flash("Intervention note added.", "success")
    return redirect(url_for("students.detail", student_id=student.id))


@students_bp.route("/interventions/<int:intervention_id>/complete", methods=["POST"])
@login_required
@role_required("admin", "lecturer")
def complete_intervention(intervention_id):
    query = InterventionLog.query.join(Student, InterventionLog.student_id == Student.id)
    if current_user.role == "lecturer":
        query = query.filter(Student.department_id == current_user.department_id)

    intervention = query.filter(InterventionLog.id == intervention_id).first_or_404()
    outcome_note = request.form.get("outcome_note", "").strip()

    from datetime import datetime
    intervention.status = "completed"
    intervention.completed_at = datetime.utcnow()
    intervention.outcome_note = outcome_note or intervention.outcome_note
    db.session.commit()

    flash("Intervention marked as completed.", "success")
    return redirect(url_for("students.detail", student_id=intervention.student_id))


@students_bp.route("/<int:student_id>/registration", methods=["GET", "POST"])
@login_required
@role_required("admin", "lecturer")
def manage_registration(student_id):
    student = _student_query_for_current_user().filter_by(id=student_id).first_or_404()

    if request.method == "POST":
        year_of_study = request.form.get("year_of_study", "").strip()
        academic_year, term_type, term_name, unit_ids = _extract_registration_form(request)

        try:
            year_value = int(year_of_study)
        except ValueError:
            flash("Year of study must be a valid whole number.", "danger")
            return render_template(
                "students/registration_form.html",
                student=student,
                registration_history=_build_registration_snapshot(student),
                current_registration_ids=_current_registration_ids(student),
                **_term_context(),
            )

        registration_error = _validate_registration(student.course, term_type, term_name, unit_ids)
        if registration_error:
            flash(registration_error, "danger")
            return render_template(
                "students/registration_form.html",
                student=student,
                registration_history=_build_registration_snapshot(student),
                current_registration_ids=_current_registration_ids(student),
                **_term_context(),
            )

        student.year_of_study = year_value
        student.academic_year = academic_year
        student.term_type = term_type
        student.semester = term_name
        _replace_registrations_for_term(student, academic_year, term_type, term_name, unit_ids)
        db.session.commit()

        flash("Academic placement and unit registration updated.", "success")
        return redirect(url_for("students.detail", student_id=student.id))

    return render_template(
        "students/registration_form.html",
        student=student,
        registration_history=_build_registration_snapshot(student),
        current_registration_ids=_current_registration_ids(student),
        **_term_context(),
    )
