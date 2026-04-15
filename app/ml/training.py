import json
import os

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..models import Student, AcademicRecord, QuestionnaireResponse
from ..extensions import db


ARTIFACTS_DIR = "artifacts"
MODEL_FILE = os.path.join(ARTIFACTS_DIR, "best_model.pkl")
META_FILE = os.path.join(ARTIFACTS_DIR, "model_meta.json")
IMPORTANCE_FILE = os.path.join(ARTIFACTS_DIR, "feature_importance.json")


FEATURE_COLUMNS = [
    "marks",
    "attendance_percent",
    "coursework_mark",
    "exam_mark",
    "year_of_study",
    "attendance_frequency",
    "coursework_on_time",
    "main_challenge",
    "early_warning_helpful",
    "study_hours_per_week",
]

NUMERIC_FEATURES = [
    "marks",
    "attendance_percent",
    "coursework_mark",
    "exam_mark",
    "year_of_study",
    "study_hours_per_week",
]

CATEGORICAL_FEATURES = [
    "attendance_frequency",
    "coursework_on_time",
    "main_challenge",
    "early_warning_helpful",
]


def _ensure_artifacts_dir():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def _derive_risk_label(final_mark, attendance_percent, coursework_total, study_hours, main_challenge, coursework_on_time):
    score = 0

    if final_mark < 40:
        score += 3
    elif final_mark < 50:
        score += 2
    elif final_mark < 60:
        score += 1

    if attendance_percent < 50:
        score += 3
    elif attendance_percent < 70:
        score += 2
    elif attendance_percent < 80:
        score += 1

    if coursework_total < 15:
        score += 2
    elif coursework_total < 21:
        score += 1

    if study_hours < 5:
        score += 2
    elif study_hours < 10:
        score += 1

    if main_challenge in {"Financial", "Health", "Family Responsibilities", "Transport"}:
        score += 1

    if coursework_on_time in {"Rarely", "No", "Late"}:
        score += 2
    elif coursework_on_time == "Sometimes":
        score += 1

    if score >= 6:
        return "High Risk"
    if score >= 3:
        return "Medium Risk"
    return "Low Risk"


def _build_dataframe():
    rows = []

    students = Student.query.all()
    for student in students:
        record = (
            AcademicRecord.query.filter_by(student_id=student.id)
            .order_by(AcademicRecord.created_at.desc())
            .first()
        )
        response = (
            QuestionnaireResponse.query.filter_by(student_id=student.id)
            .order_by(QuestionnaireResponse.created_at.desc())
            .first()
        )

        if not record or not response:
            continue

        final_mark = float(record.final_mark or 0.0)
        attendance_percent = float(record.attendance_percent or 0.0)
        coursework_total = float(record.coursework_total or 0.0)
        exam_mark = float(record.exam_mark or 0.0)
        study_hours = float(response.study_hours_per_week or 0.0)

        row = {
            "marks": final_mark,
            "attendance_percent": attendance_percent,
            "coursework_mark": coursework_total,
            "exam_mark": exam_mark,
            "year_of_study": int(student.year_of_study or 1),
            "attendance_frequency": response.attendance_frequency,
            "coursework_on_time": response.coursework_on_time,
            "main_challenge": response.main_challenge,
            "early_warning_helpful": response.early_warning_helpful,
            "study_hours_per_week": study_hours,
            "label": _derive_risk_label(
                final_mark=final_mark,
                attendance_percent=attendance_percent,
                coursework_total=coursework_total,
                study_hours=study_hours,
                main_challenge=str(response.main_challenge or ""),
                coursework_on_time=str(response.coursework_on_time or ""),
            ),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def train_and_save_model():
    _ensure_artifacts_dir()

    df = _build_dataframe()

    if df.empty or len(df) < 12:
        meta = {
            "ready": False,
            "record_count": int(len(df)),
            "threshold": 0.55,
            "feature_columns": FEATURE_COLUMNS,
            "message": "Not enough complete learner records to train the model yet.",
            "test_f1_weighted": 0.0,
            "test_balanced_accuracy": 0.0,
        }

        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        with open(IMPORTANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

        return meta

    X = df[FEATURE_COLUMNS]
    y = df["label"]

    if len(set(y)) < 2:
        meta = {
            "ready": False,
            "record_count": int(len(df)),
            "threshold": 0.55,
            "feature_columns": FEATURE_COLUMNS,
            "message": "Training requires at least two risk classes in the data.",
            "test_f1_weighted": 0.0,
            "test_balanced_accuracy": 0.0,
        }

        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        with open(IMPORTANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

        return meta

    stratify_target = y if y.value_counts().min() >= 2 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.25,
        random_state=42,
        stratify=stratify_target,
    )

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERIC_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=300,
                    max_depth=10,
                    random_state=42,
                    class_weight="balanced_subsample",
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)

    weighted_f1 = float(f1_score(y_test, predictions, average="weighted"))
    balanced_acc = float(balanced_accuracy_score(y_test, predictions))

    classifier = model.named_steps["classifier"]
    importances = classifier.feature_importances_

    preprocessor_fitted = model.named_steps["preprocessor"]
    feature_names = preprocessor_fitted.get_feature_names_out()
    feature_importance = {
        str(name): float(score) for name, score in zip(feature_names, importances)
    }

    grouped_importance = {
        "marks": 0.0,
        "attendance_percent": 0.0,
        "coursework_mark": 0.0,
        "exam_mark": 0.0,
        "year_of_study": 0.0,
        "attendance_frequency": 0.0,
        "coursework_on_time": 0.0,
        "main_challenge": 0.0,
        "early_warning_helpful": 0.0,
        "study_hours_per_week": 0.0,
    }

    for name, value in feature_importance.items():
        cleaned = name
        if cleaned.startswith("num__"):
            cleaned = cleaned.replace("num__", "")
            grouped_importance[cleaned] += value
        elif cleaned.startswith("cat__"):
            cleaned = cleaned.replace("cat__", "")
            base = cleaned.split("_")[0]
            if base in grouped_importance:
                grouped_importance[base] += value

    threshold = 0.55

    meta = {
        "ready": True,
        "record_count": int(len(df)),
        "threshold": threshold,
        "feature_columns": FEATURE_COLUMNS,
        "message": "Model trained successfully on current learner records.",
        "test_f1_weighted": weighted_f1,
        "test_balanced_accuracy": balanced_acc,
        "label_distribution": {str(k): int(v) for k, v in y.value_counts().to_dict().items()},
        "classification_report": classification_report(y_test, predictions, output_dict=True),
    }

    joblib.dump(model, MODEL_FILE)

    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    with open(IMPORTANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(grouped_importance, f, indent=2)

    return meta