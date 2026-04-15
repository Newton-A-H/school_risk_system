import json
import os
from ..models import RiskPrediction
from ..ml.training import META_FILE, IMPORTANCE_FILE


def dashboard_payload():
    predictions = RiskPrediction.query.all()
    risk_counts = {'Low Risk': 0, 'Medium Risk': 0, 'High Risk': 0}
    for item in predictions:
        risk_counts[item.predicted_risk] = risk_counts.get(item.predicted_risk, 0) + 1

    feature_importance = {}
    if os.path.exists(IMPORTANCE_FILE):
        with open(IMPORTANCE_FILE, 'r', encoding='utf-8') as f:
            feature_importance = json.load(f)

    model_meta = {}
    if os.path.exists(META_FILE):
        with open(META_FILE, 'r', encoding='utf-8') as f:
            model_meta = json.load(f)

    return {
        'risk_counts': risk_counts,
        'feature_importance': feature_importance,
        'model_meta': model_meta,
    }
