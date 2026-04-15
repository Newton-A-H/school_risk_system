import json
import os

import joblib
import pandas as pd


ARTIFACTS_DIR = "artifacts"
MODEL_FILE = os.path.join(ARTIFACTS_DIR, "best_model.pkl")
META_FILE = os.path.join(ARTIFACTS_DIR, "model_meta.json")


def _load_meta():
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "ready": False,
        "threshold": 0.55,
        "feature_columns": [
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
        ],
        "message": "Model metadata not found. Using fallback rules.",
    }


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _fallback_prediction(payload):
    marks = _safe_float(payload.get("marks"), 0.0)
    attendance = _safe_float(payload.get("attendance_percent"), 0.0)
    coursework_mark = _safe_float(payload.get("coursework_mark"), 0.0)
    exam_mark = _safe_float(payload.get("exam_mark"), 0.0)
    study_hours = _safe_float(payload.get("study_hours_per_week"), 0.0)

    attendance_frequency = str(payload.get("attendance_frequency") or "")
    coursework_on_time = str(payload.get("coursework_on_time") or "")
    main_challenge = str(payload.get("main_challenge") or "")
    early_warning_helpful = str(payload.get("early_warning_helpful") or "")

    risk_score = 0

    if marks < 40:
        risk_score += 3
    elif marks < 50:
        risk_score += 2
    elif marks < 60:
        risk_score += 1

    if attendance < 50:
        risk_score += 3
    elif attendance < 70:
        risk_score += 2
    elif attendance < 80:
        risk_score += 1

    if coursework_mark < 15:
        risk_score += 2
    elif coursework_mark < 21:
        risk_score += 1

    if exam_mark < 35:
        risk_score += 2
    elif exam_mark < 45:
        risk_score += 1

    if study_hours < 5:
        risk_score += 2
    elif study_hours < 10:
        risk_score += 1

    if attendance_frequency in {"Rarely", "Sometimes"}:
        risk_score += 1

    if coursework_on_time in {"Rarely", "No", "Late"}:
        risk_score += 2
    elif coursework_on_time == "Sometimes":
        risk_score += 1

    if main_challenge in {"Financial", "Health", "Family Responsibilities", "Transport"}:
        risk_score += 1

    if early_warning_helpful == "Yes":
        risk_score += 0.5

    if risk_score >= 6:
        risk_level = "High Risk"
        probs = {"Low Risk": 0.08, "Medium Risk": 0.20, "High Risk": 0.72}
    elif risk_score >= 3:
        risk_level = "Medium Risk"
        probs = {"Low Risk": 0.20, "Medium Risk": 0.60, "High Risk": 0.20}
    else:
        risk_level = "Low Risk"
        probs = {"Low Risk": 0.76, "Medium Risk": 0.19, "High Risk": 0.05}

    meta = _load_meta()

    return {
        "risk_level": risk_level,
        "probabilities": probs,
        "threshold": float(meta.get("threshold", 0.55)),
        "meta": {
            "ready": False,
            "message": "Fallback rules used because trained model is unavailable.",
        },
    }


def predict_record(payload):
    meta = _load_meta()

    if not os.path.exists(MODEL_FILE):
        return _fallback_prediction(payload)

    try:
        model = joblib.load(MODEL_FILE)
        feature_columns = meta.get("feature_columns", [])

        if not feature_columns:
            return _fallback_prediction(payload)

        row = {feature: payload.get(feature) for feature in feature_columns}
        X = pd.DataFrame([row], columns=feature_columns)

        predicted_class = model.predict(X)[0]
        class_probabilities = model.predict_proba(X)[0]
        classes = list(model.classes_)

        probs = {str(cls): float(prob) for cls, prob in zip(classes, class_probabilities)}

        threshold = float(meta.get("threshold", 0.55))
        high_risk_probability = probs.get("High Risk", 0.0)

        risk_level = str(predicted_class)
        if high_risk_probability >= threshold:
            risk_level = "High Risk"
        elif high_risk_probability >= 0.25 and risk_level == "Low Risk":
            risk_level = "Medium Risk"

        return {
            "risk_level": risk_level,
            "probabilities": {
                "Low Risk": probs.get("Low Risk", 0.0),
                "Medium Risk": probs.get("Medium Risk", 0.0),
                "High Risk": probs.get("High Risk", 0.0),
            },
            "threshold": threshold,
            "meta": {
                "ready": True,
                "message": meta.get("message", "Prediction generated using the trained model."),
            },
        }

    except Exception:
        return _fallback_prediction(payload)