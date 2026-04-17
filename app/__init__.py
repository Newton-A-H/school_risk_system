from flask import Flask
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager, migrate
from .models import FeedbackConversation, AccountRequest, Student, AcademicRecord, InterventionLog, RiskPrediction
from .services.rate_limit import check_rate_limit


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

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

    @app.before_request
    def apply_rate_limit():
        return check_rate_limit()

    @app.context_processor
    def inject_feedback_conversation():
        conversation = None
        support_badges = {
            "admin_unread_count": 0,
            "user_unread_count": 0,
        }
        notification_count = 0

        try:
            if current_user.is_authenticated:
                if current_user.role == "admin":
                    conversations = FeedbackConversation.query.all()
                    support_badges["admin_unread_count"] = sum(
                        1
                        for item in conversations
                        if item.last_user_message_at
                        and (
                            item.last_read_by_admin_at is None
                            or item.last_user_message_at > item.last_read_by_admin_at
                        )
                    )
                    notification_count = support_badges["admin_unread_count"]
                    notification_count += AccountRequest.query.filter_by(status="pending").count()
                else:
                    user_conversations = (
                        FeedbackConversation.query.filter_by(user_id=current_user.id)
                        .order_by(FeedbackConversation.last_message_at.desc())
                        .all()
                    )
                    if user_conversations:
                        conversation = user_conversations[0]
                    support_badges["user_unread_count"] = sum(
                        1
                        for item in user_conversations
                        if item.last_admin_message_at
                        and (
                            item.last_read_by_user_at is None
                            or item.last_admin_message_at > item.last_read_by_user_at
                        )
                    )
                    notification_count = support_badges["user_unread_count"]

                    if current_user.role == "student":
                        student = Student.query.filter_by(user_id=current_user.id).first()
                        if not student and current_user.email:
                            student = Student.query.filter_by(email=current_user.email).first()
                        if student:
                            notification_count += InterventionLog.query.filter_by(student_id=student.id, status="planned").count()
                    elif current_user.role == "lecturer" and current_user.department_id:
                        notification_count += (
                            AcademicRecord.query.join(Student, AcademicRecord.student_id == Student.id)
                            .filter(
                                Student.department_id == current_user.department_id,
                                AcademicRecord.is_verified == False,
                            )
                            .count()
                        )
                        student_ids = [
                            item.id for item in Student.query.filter_by(department_id=current_user.department_id).all()
                        ]
                        if student_ids:
                            notification_count += (
                                RiskPrediction.query.filter(
                                    RiskPrediction.student_id.in_(student_ids),
                                    RiskPrediction.predicted_risk == "High Risk",
                                ).count()
                            )
        except Exception:
            conversation = None

        return {
            "feedback_conversation": conversation,
            "support_badges": support_badges,
            "notification_count": notification_count,
        }

    with app.app_context():
        from .services.startup import validate_runtime_config

        if app.config.get("VALIDATE_STARTUP", True):
            for issue in validate_runtime_config(app):
                app.logger.warning("Startup validation: %s", issue)

        if app.config.get("BOOTSTRAP_DATABASE", True):
            from .services.db_bootstrap import bootstrap_database
            bootstrap_database()

    return app
