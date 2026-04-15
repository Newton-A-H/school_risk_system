from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

try:
    from flask_migrate import Migrate
except ModuleNotFoundError:
    class Migrate:  # pragma: no cover - fallback for environments without Flask-Migrate installed
        def init_app(self, app, db):
            return None

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
