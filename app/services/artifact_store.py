import os


ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", "artifacts")
MODEL_FILE = os.path.join(ARTIFACTS_DIR, "best_model.pkl")
META_FILE = os.path.join(ARTIFACTS_DIR, "model_meta.json")
IMPORTANCE_FILE = os.path.join(ARTIFACTS_DIR, "feature_importance.json")
HISTORY_FILE = os.path.join(ARTIFACTS_DIR, "model_history.json")


def ensure_artifacts_dir():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
