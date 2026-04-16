from flask import current_app

from ..extensions import db


def bootstrap_database():
    """
    Ensure the SQLAlchemy-managed schema exists for PostgreSQL-friendly setups.

    The project now relies on the ORM metadata for schema creation rather than
    SQL Server-specific ALTER/INFORMATION_SCHEMA logic.
    """
    db.create_all()
    db.session.commit()
    current_app.logger.info(
        "Database bootstrap completed successfully using the %s dialect.",
        db.engine.dialect.name,
    )
