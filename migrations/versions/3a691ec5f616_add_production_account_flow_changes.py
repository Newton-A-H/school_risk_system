"""add production account flow changes"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "3a691ec5f616"
down_revision = None
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS count_value
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = :table_name AND COLUMN_NAME = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar()
    return int(result or 0) > 0


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS count_value
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = :table_name
            """
        ),
        {"table_name": table_name},
    ).scalar()
    return int(result or 0) > 0


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) AS count_value
            FROM sys.indexes
            WHERE name = :index_name
              AND object_id = OBJECT_ID(:table_name)
            """
        ),
        {"index_name": index_name, "table_name": table_name},
    ).scalar()
    return int(result or 0) > 0


def drop_default_constraint(table_name: str, column_name: str) -> None:
    op.execute(
        f"""
        DECLARE @constraint_name NVARCHAR(200);

        SELECT @constraint_name = dc.name
        FROM sys.default_constraints dc
        INNER JOIN sys.columns c
            ON c.default_object_id = dc.object_id
        INNER JOIN sys.tables t
            ON t.object_id = c.object_id
        WHERE t.name = '{table_name}'
          AND c.name = '{column_name}';

        IF @constraint_name IS NOT NULL
            EXEC('ALTER TABLE {table_name} DROP CONSTRAINT ' + @constraint_name);
        """
    )


def safe_drop_column(table_name: str, batch_op, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        drop_default_constraint(table_name, column_name)
        batch_op.drop_column(column_name)


def _ensure_default_department_and_course():
    if _table_exists("departments"):
        op.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM departments)
            BEGIN
                INSERT INTO departments (name, code)
                VALUES ('General Department', 'GEN')
            END
            """
        )

    if _table_exists("courses") and _table_exists("departments"):
        op.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM courses)
            BEGIN
                INSERT INTO courses (department_id, name, code)
                VALUES (
                    (SELECT TOP 1 id FROM departments ORDER BY id),
                    'General Course',
                    'GEN101'
                )
            END
            """
        )


def upgrade():
    # -------------------------------------------------
    # CREATE SAFETY DATA IF NEEDED
    # -------------------------------------------------
    _ensure_default_department_and_course()

    # -------------------------------------------------
    # DATA FIXES FIRST
    # -------------------------------------------------
    if _column_exists("academic_records", "assignment_mark"):
        op.execute(
            """
            UPDATE academic_records
            SET assignment_mark = 0
            WHERE assignment_mark IS NULL
            """
        )

    if _column_exists("academic_records", "cat_mark"):
        op.execute(
            """
            UPDATE academic_records
            SET cat_mark = 0
            WHERE cat_mark IS NULL
            """
        )

    if _column_exists("academic_records", "exam_mark"):
        op.execute(
            """
            UPDATE academic_records
            SET exam_mark = 0
            WHERE exam_mark IS NULL
            """
        )

    if _column_exists("academic_records", "coursework_total"):
        op.execute(
            """
            UPDATE academic_records
            SET coursework_total = ISNULL(assignment_mark, 0) + ISNULL(cat_mark, 0)
            WHERE coursework_total IS NULL
            """
        )

    if _column_exists("academic_records", "final_mark"):
        op.execute(
            """
            UPDATE academic_records
            SET final_mark = ISNULL(coursework_total, 0) + ISNULL(exam_mark, 0)
            WHERE final_mark IS NULL
            """
        )

    if _column_exists("risk_predictions", "created_by") and _table_exists("users"):
        op.execute(
            """
            UPDATE risk_predictions
            SET created_by = (
                SELECT TOP 1 id FROM users ORDER BY id
            )
            WHERE created_by IS NULL
              AND EXISTS (SELECT 1 FROM users)
            """
        )

    if _column_exists("students", "department_id") and _table_exists("departments"):
        op.execute(
            """
            UPDATE students
            SET department_id = (
                SELECT TOP 1 id FROM departments ORDER BY id
            )
            WHERE department_id IS NULL
              AND EXISTS (SELECT 1 FROM departments)
            """
        )

    if _column_exists("students", "course_id") and _table_exists("courses"):
        op.execute(
            """
            UPDATE students
            SET course_id = (
                SELECT TOP 1 id FROM courses ORDER BY id
            )
            WHERE course_id IS NULL
              AND EXISTS (SELECT 1 FROM courses)
            """
        )

    # -------------------------------------------------
    # academic_records
    # -------------------------------------------------
    if _column_exists("academic_records", "created_at"):
        drop_default_constraint("academic_records", "created_at")
    if _column_exists("academic_records", "updated_at"):
        drop_default_constraint("academic_records", "updated_at")

    with op.batch_alter_table("academic_records", schema=None) as batch_op:
        if _column_exists("academic_records", "cat_mark"):
            batch_op.alter_column(
                "cat_mark",
                existing_type=sa.FLOAT(precision=53),
                nullable=False,
            )

        if _column_exists("academic_records", "coursework_total"):
            batch_op.alter_column(
                "coursework_total",
                existing_type=sa.FLOAT(precision=53),
                nullable=False,
            )

        if _column_exists("academic_records", "final_mark"):
            batch_op.alter_column(
                "final_mark",
                existing_type=sa.FLOAT(precision=53),
                nullable=False,
            )

        if _column_exists("academic_records", "teacher_comment"):
            batch_op.alter_column(
                "teacher_comment",
                existing_type=sa.NVARCHAR(length=255, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.Text(),
                existing_nullable=True,
            )

        if _column_exists("academic_records", "created_at"):
            batch_op.alter_column(
                "created_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        safe_drop_column("academic_records", batch_op, "marks_out_of_100")
        safe_drop_column("academic_records", batch_op, "coursework_mark")
        safe_drop_column("academic_records", batch_op, "updated_at")

    # -------------------------------------------------
    # questionnaire_responses
    # -------------------------------------------------
    if _column_exists("questionnaire_responses", "created_at"):
        drop_default_constraint("questionnaire_responses", "created_at")
    if _column_exists("questionnaire_responses", "updated_at"):
        drop_default_constraint("questionnaire_responses", "updated_at")

    with op.batch_alter_table("questionnaire_responses", schema=None) as batch_op:
        if _column_exists("questionnaire_responses", "attendance_frequency"):
            batch_op.alter_column(
                "attendance_frequency",
                existing_type=sa.NVARCHAR(length=30, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.String(length=50),
                existing_nullable=False,
            )

        if _column_exists("questionnaire_responses", "coursework_on_time"):
            batch_op.alter_column(
                "coursework_on_time",
                existing_type=sa.NVARCHAR(length=30, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.String(length=50),
                existing_nullable=False,
            )

        if _column_exists("questionnaire_responses", "main_challenge"):
            batch_op.alter_column(
                "main_challenge",
                existing_type=sa.NVARCHAR(length=80, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.String(length=100),
                existing_nullable=False,
            )

        if _column_exists("questionnaire_responses", "early_warning_helpful"):
            batch_op.alter_column(
                "early_warning_helpful",
                existing_type=sa.NVARCHAR(length=10, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.String(length=20),
                existing_nullable=False,
            )

        if _column_exists("questionnaire_responses", "created_at"):
            batch_op.alter_column(
                "created_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        safe_drop_column("questionnaire_responses", batch_op, "updated_at")

    # -------------------------------------------------
    # risk_predictions
    # -------------------------------------------------
    if _column_exists("risk_predictions", "created_at"):
        drop_default_constraint("risk_predictions", "created_at")
    if _column_exists("risk_predictions", "updated_at"):
        drop_default_constraint("risk_predictions", "updated_at")

    with op.batch_alter_table("risk_predictions", schema=None) as batch_op:
        if _column_exists("risk_predictions", "predicted_risk"):
            batch_op.alter_column(
                "predicted_risk",
                existing_type=sa.NVARCHAR(length=20, collation="SQL_Latin1_General_CP1_CI_AS"),
                type_=sa.String(length=30),
                existing_nullable=False,
            )

        if _column_exists("risk_predictions", "created_by"):
            batch_op.alter_column(
                "created_by",
                existing_type=sa.INTEGER(),
                nullable=False,
            )

        if _column_exists("risk_predictions", "created_at"):
            batch_op.alter_column(
                "created_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        safe_drop_column("risk_predictions", batch_op, "updated_at")

    # -------------------------------------------------
    # students
    # -------------------------------------------------
    if _column_exists("students", "created_at"):
        drop_default_constraint("students", "created_at")
    if _column_exists("students", "updated_at"):
        drop_default_constraint("students", "updated_at")

    # last safety pass before NOT NULL
    if _column_exists("students", "department_id") and _table_exists("departments"):
        op.execute(
            """
            UPDATE students
            SET department_id = (
                SELECT TOP 1 id FROM departments ORDER BY id
            )
            WHERE department_id IS NULL
              AND EXISTS (SELECT 1 FROM departments)
            """
        )

    if _column_exists("students", "course_id") and _table_exists("courses"):
        op.execute(
            """
            UPDATE students
            SET course_id = (
                SELECT TOP 1 id FROM courses ORDER BY id
            )
            WHERE course_id IS NULL
              AND EXISTS (SELECT 1 FROM courses)
            """
        )

    with op.batch_alter_table("students", schema=None) as batch_op:
        if _column_exists("students", "department_id"):
            batch_op.alter_column(
                "department_id",
                existing_type=sa.INTEGER(),
                nullable=False,
            )

        if _column_exists("students", "course_id"):
            batch_op.alter_column(
                "course_id",
                existing_type=sa.INTEGER(),
                nullable=False,
            )

        if _column_exists("students", "created_at"):
            batch_op.alter_column(
                "created_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        if not _index_exists("students", "ix_students_admission_no"):
            batch_op.create_index("ix_students_admission_no", ["admission_no"], unique=True)

        safe_drop_column("students", batch_op, "course_name")
        safe_drop_column("students", batch_op, "updated_at")

    # -------------------------------------------------
    # users
    # -------------------------------------------------
    if _column_exists("users", "created_at"):
        drop_default_constraint("users", "created_at")
    if _column_exists("users", "updated_at"):
        drop_default_constraint("users", "updated_at")

    with op.batch_alter_table("users", schema=None) as batch_op:
        if _column_exists("users", "created_at"):
            batch_op.alter_column(
                "created_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        if _column_exists("users", "updated_at"):
            batch_op.alter_column(
                "updated_at",
                existing_type=mssql.DATETIME2(),
                type_=sa.DateTime(),
                existing_nullable=False,
            )

        if not _index_exists("users", "ix_users_email"):
            batch_op.create_index("ix_users_email", ["email"], unique=True)


def downgrade():
    # intentionally omitted for safety
    pass