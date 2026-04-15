from sqlalchemy import text
from flask import current_app

from ..extensions import db


def _column_exists(table_name, column_name):
    sql = text("""
        SELECT COUNT(*) AS count_value
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
    """)
    result = db.session.execute(sql, {"table_name": table_name, "column_name": column_name}).scalar()
    return int(result or 0) > 0


def _table_exists(table_name):
    sql = text("""
        SELECT COUNT(*) AS count_value
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = :table_name
    """)
    result = db.session.execute(sql, {"table_name": table_name}).scalar()
    return int(result or 0) > 0


def _fk_exists(fk_name):
    sql = text("""
        SELECT COUNT(*) AS count_value
        FROM sys.foreign_keys
        WHERE name = :fk_name
    """)
    result = db.session.execute(sql, {"fk_name": fk_name}).scalar()
    return int(result or 0) > 0


def bootstrap_database():
    """
    Automatic SQL Server bootstrap/update for common schema changes.
    This avoids manually going to SSMS for each new column/table.
    """
    # Create base tables from models first
    db.create_all()

    # ----------------------------
    # users table updates
    # ----------------------------
    if not _column_exists("users", "is_verified"):
        db.session.execute(text("ALTER TABLE users ADD is_verified BIT NOT NULL CONSTRAINT DF_users_is_verified DEFAULT 0"))
    if not _column_exists("users", "verification_token"):
        db.session.execute(text("ALTER TABLE users ADD verification_token NVARCHAR(255) NULL"))

    # ----------------------------
    # departments table
    # ----------------------------
    if not _table_exists("departments"):
        db.session.execute(text("""
            CREATE TABLE departments (
                id INT IDENTITY(1,1) PRIMARY KEY,
                name NVARCHAR(150) NOT NULL UNIQUE,
                code NVARCHAR(30) NOT NULL UNIQUE
            )
        """))

    # ----------------------------
    # courses table
    # ----------------------------
    if not _table_exists("courses"):
        db.session.execute(text("""
            CREATE TABLE courses (
                id INT IDENTITY(1,1) PRIMARY KEY,
                department_id INT NOT NULL,
                name NVARCHAR(150) NOT NULL,
                code NVARCHAR(30) NOT NULL UNIQUE
            )
        """))

    if not _fk_exists("FK_courses_department_id"):
        db.session.execute(text("""
            ALTER TABLE courses
            ADD CONSTRAINT FK_courses_department_id
            FOREIGN KEY (department_id) REFERENCES departments(id)
        """))

    # ----------------------------
    # students table updates
    # ----------------------------
    if not _column_exists("students", "user_id"):
        db.session.execute(text("ALTER TABLE students ADD user_id INT NULL"))
    if not _column_exists("students", "lecturer_user_id"):
        db.session.execute(text("ALTER TABLE students ADD lecturer_user_id INT NULL"))
    if not _column_exists("students", "department_id"):
        db.session.execute(text("ALTER TABLE students ADD department_id INT NULL"))
    if not _column_exists("students", "course_id"):
        db.session.execute(text("ALTER TABLE students ADD course_id INT NULL"))

    if not _fk_exists("FK_students_user_id"):
        db.session.execute(text("""
            ALTER TABLE students
            ADD CONSTRAINT FK_students_user_id
            FOREIGN KEY (user_id) REFERENCES users(id)
        """))
    if not _fk_exists("FK_students_lecturer_user_id"):
        db.session.execute(text("""
            ALTER TABLE students
            ADD CONSTRAINT FK_students_lecturer_user_id
            FOREIGN KEY (lecturer_user_id) REFERENCES users(id)
        """))
    if not _fk_exists("FK_students_department_id"):
        db.session.execute(text("""
            ALTER TABLE students
            ADD CONSTRAINT FK_students_department_id
            FOREIGN KEY (department_id) REFERENCES departments(id)
        """))
    if not _fk_exists("FK_students_course_id"):
        db.session.execute(text("""
            ALTER TABLE students
            ADD CONSTRAINT FK_students_course_id
            FOREIGN KEY (course_id) REFERENCES courses(id)
        """))

    # ----------------------------
    # academic_records updates
    # ----------------------------
    if not _column_exists("academic_records", "assignment_mark"):
        db.session.execute(text("ALTER TABLE academic_records ADD assignment_mark FLOAT NULL"))
    if not _column_exists("academic_records", "cat_mark"):
        db.session.execute(text("ALTER TABLE academic_records ADD cat_mark FLOAT NULL"))
    if not _column_exists("academic_records", "coursework_total"):
        db.session.execute(text("ALTER TABLE academic_records ADD coursework_total FLOAT NULL"))
    if not _column_exists("academic_records", "final_mark"):
        db.session.execute(text("ALTER TABLE academic_records ADD final_mark FLOAT NULL"))

    # ----------------------------
    # account_requests table
    # ----------------------------
    if not _table_exists("account_requests"):
        db.session.execute(text("""
            CREATE TABLE account_requests (
                id INT IDENTITY(1,1) PRIMARY KEY,
                full_name NVARCHAR(150) NOT NULL,
                email NVARCHAR(150) NOT NULL UNIQUE,
                requested_role NVARCHAR(30) NOT NULL,
                department_id INT NULL,
                course_id INT NULL,
                status NVARCHAR(30) NOT NULL DEFAULT 'pending',
                verification_token NVARCHAR(255) NULL,
                is_email_verified BIT NOT NULL DEFAULT 0,
                created_at DATETIME2 NOT NULL DEFAULT GETDATE()
            )
        """))

    if not _fk_exists("FK_account_requests_department_id"):
        db.session.execute(text("""
            ALTER TABLE account_requests
            ADD CONSTRAINT FK_account_requests_department_id
            FOREIGN KEY (department_id) REFERENCES departments(id)
        """))

    if not _fk_exists("FK_account_requests_course_id"):
        db.session.execute(text("""
            ALTER TABLE account_requests
            ADD CONSTRAINT FK_account_requests_course_id
            FOREIGN KEY (course_id) REFERENCES courses(id)
        """))

    # ----------------------------
    # feedback conversations updates
    # ----------------------------
    if _table_exists("feedback_conversations"):
        if not _column_exists("feedback_conversations", "last_user_message_at"):
            db.session.execute(text("ALTER TABLE feedback_conversations ADD last_user_message_at DATETIME2 NULL"))
        if not _column_exists("feedback_conversations", "last_admin_message_at"):
            db.session.execute(text("ALTER TABLE feedback_conversations ADD last_admin_message_at DATETIME2 NULL"))
        if not _column_exists("feedback_conversations", "last_read_by_user_at"):
            db.session.execute(text("ALTER TABLE feedback_conversations ADD last_read_by_user_at DATETIME2 NULL"))
        if not _column_exists("feedback_conversations", "last_read_by_admin_at"):
            db.session.execute(text("ALTER TABLE feedback_conversations ADD last_read_by_admin_at DATETIME2 NULL"))

    # ----------------------------
    # intervention_logs table
    # ----------------------------
    if not _table_exists("intervention_logs"):
        db.session.execute(text("""
            CREATE TABLE intervention_logs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                student_id INT NOT NULL,
                created_by INT NOT NULL,
                title NVARCHAR(150) NOT NULL,
                note NVARCHAR(MAX) NOT NULL,
                status NVARCHAR(30) NOT NULL DEFAULT 'planned',
                follow_up_date DATETIME2 NULL,
                completed_at DATETIME2 NULL,
                outcome_note NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT GETDATE(),
                updated_at DATETIME2 NOT NULL DEFAULT GETDATE()
            )
        """))

    if not _fk_exists("FK_intervention_logs_student_id"):
        db.session.execute(text("""
            ALTER TABLE intervention_logs
            ADD CONSTRAINT FK_intervention_logs_student_id
            FOREIGN KEY (student_id) REFERENCES students(id)
        """))

    if not _fk_exists("FK_intervention_logs_created_by"):
        db.session.execute(text("""
            ALTER TABLE intervention_logs
            ADD CONSTRAINT FK_intervention_logs_created_by
            FOREIGN KEY (created_by) REFERENCES users(id)
        """))

    # ----------------------------
    # audit_logs table
    # ----------------------------
    if not _table_exists("audit_logs"):
        db.session.execute(text("""
            CREATE TABLE audit_logs (
                id INT IDENTITY(1,1) PRIMARY KEY,
                actor_user_id INT NULL,
                action NVARCHAR(120) NOT NULL,
                target_type NVARCHAR(80) NOT NULL,
                target_id INT NULL,
                detail NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT GETDATE()
            )
        """))

    if not _fk_exists("FK_audit_logs_actor_user_id"):
        db.session.execute(text("""
            ALTER TABLE audit_logs
            ADD CONSTRAINT FK_audit_logs_actor_user_id
            FOREIGN KEY (actor_user_id) REFERENCES users(id)
        """))

    db.session.commit()
    current_app.logger.info("Database bootstrap completed successfully.")
