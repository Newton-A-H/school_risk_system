from itsdangerous import URLSafeTimedSerializer
from flask import current_app


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_token(payload: str, salt: str) -> str:
    return _serializer().dumps(payload, salt=salt)


def verify_token(token: str, salt: str, max_age: int = 86400):
    try:
        return _serializer().loads(token, salt=salt, max_age=max_age)
    except Exception:
        return None