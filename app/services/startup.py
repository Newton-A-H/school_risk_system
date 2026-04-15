def validate_runtime_config(app):
    issues = []

    database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    secret_key = app.config.get("SECRET_KEY", "")

    if not database_uri:
        issues.append("DATABASE_URL is missing.")

    if secret_key in {"", "dev-secret-key"} and not app.config.get("TESTING"):
        issues.append("SECRET_KEY is using the default development value.")

    if app.config.get("MAIL_ENABLED"):
        required_mail_settings = [
            "MAIL_SERVER",
            "MAIL_PORT",
            "MAIL_USERNAME",
            "MAIL_PASSWORD",
            "MAIL_DEFAULT_SENDER",
        ]
        missing = [key for key in required_mail_settings if not app.config.get(key)]
        if missing:
            issues.append(f"Mail is enabled but these settings are missing: {', '.join(missing)}.")

    return issues
