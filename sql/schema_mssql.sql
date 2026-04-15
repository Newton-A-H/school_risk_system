CREATE DATABASE AcademicRiskDB;
GO
USE AcademicRiskDB;
GO

CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    full_name NVARCHAR(150) NOT NULL,
    email NVARCHAR(150) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    role NVARCHAR(30) NOT NULL,
    is_active_account BIT NOT NULL DEFAULT 1,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE students (
    id INT IDENTITY(1,1) PRIMARY KEY,
    admission_no NVARCHAR(50) NOT NULL UNIQUE,
    full_name NVARCHAR(150) NOT NULL,
    gender NVARCHAR(20) NULL,
    email NVARCHAR(150) NULL,
    phone NVARCHAR(30) NULL,
    school_name NVARCHAR(150) NOT NULL,
    course_name NVARCHAR(150) NOT NULL,
    year_of_study INT NOT NULL,
    semester NVARCHAR(20) NOT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE academic_records (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id INT NOT NULL,
    term_name NVARCHAR(50) NOT NULL,
    marks_out_of_100 FLOAT NOT NULL,
    attendance_percent FLOAT NOT NULL,
    coursework_mark FLOAT NOT NULL,
    exam_mark FLOAT NOT NULL,
    teacher_comment NVARCHAR(255) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_academic_records_students FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE TABLE questionnaire_responses (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id INT NOT NULL,
    attendance_frequency NVARCHAR(30) NOT NULL,
    coursework_on_time NVARCHAR(30) NOT NULL,
    main_challenge NVARCHAR(80) NOT NULL,
    early_warning_helpful NVARCHAR(10) NOT NULL,
    study_hours_per_week FLOAT NOT NULL DEFAULT 0,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_questionnaire_students FOREIGN KEY (student_id) REFERENCES students(id)
);

CREATE TABLE risk_predictions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    student_id INT NOT NULL,
    academic_record_id INT NOT NULL,
    questionnaire_response_id INT NOT NULL,
    predicted_risk NVARCHAR(20) NOT NULL,
    high_risk_probability FLOAT NOT NULL,
    threshold_used FLOAT NOT NULL,
    recommendation NVARCHAR(MAX) NOT NULL,
    created_by INT NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_predictions_students FOREIGN KEY (student_id) REFERENCES students(id),
    CONSTRAINT FK_predictions_records FOREIGN KEY (academic_record_id) REFERENCES academic_records(id),
    CONSTRAINT FK_predictions_questionnaire FOREIGN KEY (questionnaire_response_id) REFERENCES questionnaire_responses(id),
    CONSTRAINT FK_predictions_users FOREIGN KEY (created_by) REFERENCES users(id)
);
GO
