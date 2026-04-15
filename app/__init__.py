from flask import Flask
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager, migrate
from .models import FeedbackConversation


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    from .auth.routes import auth_bp
    from .main.routes import main_bp
    from .students.routes import students_bp
    from .admin.routes import admin_bp
    from .lecturer.routes import lecturer_bp
    from .student_portal.routes import student_portal_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(student_portal_bp)

    @app.context_processor
    def inject_feedback_conversation():
        conversation = None

        try:
            if current_user.is_authenticated and current_user.role != "admin":
                conversation = (
                    FeedbackConversation.query.filter_by(user_id=current_user.id)
                    .order_by(FeedbackConversation.last_message_at.desc())
                    .first()
                )
        except Exception:
            conversation = None

        return {"feedback_conversation": conversation}

    with app.app_context():
        from .services.db_bootstrap import bootstrap_database
        bootstrap_database()

    return app