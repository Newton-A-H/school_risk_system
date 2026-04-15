from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    FloatField,
    IntegerField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=150),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=4, max=128),
        ],
    )
    submit = SubmitField("Sign in")


class StudentIntakeForm(FlaskForm):
    admission_no = StringField(
        "Admission Number",
        validators=[DataRequired(), Length(max=50)],
    )
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(max=150)],
    )
    gender = SelectField(
        "Gender",
        choices=[
            ("Male", "Male"),
            ("Female", "Female"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )
    email = StringField(
        "Student Email",
        validators=[Optional(), Email(), Length(max=150)],
    )
    phone = StringField(
        "Phone Number",
        validators=[Optional(), Length(max=30)],
    )
    school_name = StringField(
        "School Name",
        validators=[DataRequired(), Length(max=150)],
    )

    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )
    course_id = SelectField(
        "Course",
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )

    year_of_study = IntegerField(
        "Year of Study",
        validators=[DataRequired(), NumberRange(min=1, max=8)],
    )
    semester = SelectField(
        "Semester",
        choices=[
            ("Semester 1", "Semester 1"),
            ("Semester 2", "Semester 2"),
            ("Semester 3", "Semester 3"),
        ],
        validators=[DataRequired()],
    )

    term_name = StringField(
        "Term / Academic Period",
        validators=[DataRequired(), Length(max=50)],
    )

    assignment_mark = FloatField(
        "Assignment Mark (Optional)",
        validators=[Optional(), NumberRange(min=0, max=30)],
        default=0.0,
    )
    cat_mark = FloatField(
        "CAT Mark (30%)",
        validators=[DataRequired(), NumberRange(min=0, max=30)],
    )
    exam_mark = FloatField(
        "Main Exam Mark (70%)",
        validators=[DataRequired(), NumberRange(min=0, max=70)],
    )
    attendance_percent = FloatField(
        "Attendance Percentage",
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )

    teacher_comment = TextAreaField(
        "Teacher Comment",
        validators=[Optional(), Length(max=1000)],
    )

    attendance_frequency = SelectField(
        "How often does the learner attend classes?",
        choices=[
            ("Always", "Always"),
            ("Often", "Often"),
            ("Sometimes", "Sometimes"),
            ("Rarely", "Rarely"),
        ],
        validators=[DataRequired()],
    )
    coursework_on_time = SelectField(
        "How often is coursework submitted on time?",
        choices=[
            ("Always", "Always"),
            ("Often", "Often"),
            ("Sometimes", "Sometimes"),
            ("Rarely", "Rarely"),
            ("No", "No"),
        ],
        validators=[DataRequired()],
    )
    main_challenge = SelectField(
        "Main Academic Challenge",
        choices=[
            ("None", "None"),
            ("Financial", "Financial"),
            ("Time Management", "Time Management"),
            ("Transport", "Transport"),
            ("Family Responsibilities", "Family Responsibilities"),
            ("Health", "Health"),
            ("Lack of Study Materials", "Lack of Study Materials"),
            ("Language Barrier", "Language Barrier"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )
    early_warning_helpful = SelectField(
        "Would early warning support help the learner?",
        choices=[
            ("Yes", "Yes"),
            ("No", "No"),
        ],
        validators=[DataRequired()],
    )
    study_hours_per_week = FloatField(
        "Study Hours Per Week",
        validators=[DataRequired(), NumberRange(min=0, max=100)],
    )

    submit = SubmitField("Save Learner Intake")


class LecturerAccountForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(max=150)],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    submit = SubmitField("Create Lecturer Account")


class StudentAccountForm(FlaskForm):
    student_id = SelectField(
        "Learner",
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=6, max=128)],
    )
    submit = SubmitField("Create Student Account")


class DepartmentForm(FlaskForm):
    name = StringField(
        "Department Name",
        validators=[DataRequired(), Length(max=150)],
    )
    code = StringField(
        "Department Code",
        validators=[DataRequired(), Length(max=30)],
    )
    submit = SubmitField("Save Department")


class CourseForm(FlaskForm):
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[DataRequired()],
        choices=[],
    )
    name = StringField(
        "Course Name",
        validators=[DataRequired(), Length(max=150)],
    )
    code = StringField(
        "Course Code",
        validators=[DataRequired(), Length(max=30)],
    )
    submit = SubmitField("Save Course")


class AccountRequestForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(max=150)],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=150)],
    )
    requested_role = SelectField(
        "Requested Role",
        choices=[
            ("student", "Student"),
            ("lecturer", "Lecturer"),
        ],
        validators=[DataRequired()],
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
        choices=[],
    )
    course_id = SelectField(
        "Course",
        coerce=int,
        validators=[Optional()],
        choices=[],
    )
    submit = SubmitField("Request Account")