from flask import current_app
from sqlalchemy import inspect, text

from ..extensions import db


def bootstrap_database():
    """
    Ensure the SQLAlchemy-managed schema exists for PostgreSQL-friendly setups.

    The project now relies on the ORM metadata for schema creation rather than
    SQL Server-specific ALTER/INFORMATION_SCHEMA logic.
    """
    db.create_all()
    _ensure_additive_columns()
    db.session.commit()
    current_app.logger.info(
        "Database bootstrap completed successfully using the %s dialect.",
        db.engine.dialect.name,
    )


def _ensure_additive_columns():
    inspector = inspect(db.engine)
    planned_columns = {
        "students": {
            "term_type": "VARCHAR(20) NOT NULL DEFAULT 'semester'",
            "academic_year": "VARCHAR(20) NOT NULL DEFAULT ''",
        },
        "academic_records": {
            "unit_id": "INTEGER",
            "term_type": "VARCHAR(20) NOT NULL DEFAULT 'semester'",
            "academic_year": "VARCHAR(20) NOT NULL DEFAULT ''",
        },
        "questionnaire_responses": {
            "term_name": "VARCHAR(50) NOT NULL DEFAULT ''",
            "term_type": "VARCHAR(20) NOT NULL DEFAULT 'semester'",
            "academic_year": "VARCHAR(20) NOT NULL DEFAULT ''",
        },
        "account_requests": {
            "term_type": "VARCHAR(20)",
            "academic_year": "VARCHAR(20)",
        },
    }

    for table_name, columns in planned_columns.items():
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, column_sql in columns.items():
            if column_name in existing:
                continue
            db.session.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")
            )
            current_app.logger.info("Added missing column %s.%s during bootstrap.", table_name, column_name)
