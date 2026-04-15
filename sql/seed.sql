USE AcademicRiskDB;
GO
INSERT INTO users (full_name, email, password_hash, role)
VALUES ('System Administrator', 'admin@school.local', 'pbkdf2:sha256:600000$demo$replace-this-from-flask-shell', 'admin');
GO
