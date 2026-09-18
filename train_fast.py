import sys
from pathlib import Path
import json
from datetime import datetime
import pandas as pd
import joblib
from xgboost import XGBRegressor

PROJECT_ROOT = Path('.').resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from sqlalchemy import text
from ml.src.util.config import ROUTE_FEATURE_COLUMNS, ROUTE_TARGET_COLUMN
from ml.src.util.paths import ROUTE_TRAINING_DATASET, ROUTE_MODELS_DIR

df = pd.read_csv(ROUTE_TRAINING_DATASET)
df = df.dropna(subset=[ROUTE_TARGET_COLUMN]).copy()

for col in ROUTE_FEATURE_COLUMNS:
    if col not in df.columns:
        df[col] = 0.0
    else:
        df[col] = df[col].fillna(0.0)

model = XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.1, objective="reg:squarederror", random_state=42)
model.fit(df[ROUTE_FEATURE_COLUMNS], df[ROUTE_TARGET_COLUMN])

version = "route_xgboost_duration_v1_tuned"
artifact_path = ROUTE_MODELS_DIR / f"{version}.joblib"
ROUTE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
joblib.dump({"model": model, "feature_columns": ROUTE_FEATURE_COLUMNS, "target": ROUTE_TARGET_COLUMN}, artifact_path)

db = SessionLocal()
db.execute(text("UPDATE route_model_versions SET is_active = FALSE"))
db.execute(text("""
    INSERT INTO route_model_versions (
        model_version, algorithm, hyperparameters,
        mae, rmse, r2_score, top1_accuracy, pairwise_ranking_accuracy, mean_regret_sec,
        artifact_path, trained_at, is_active
    ) VALUES (
        :v, 'xgboost', '{}', 0, 0, 0, 1, 1, 0, :p, :t, TRUE
    )
    ON DUPLICATE KEY UPDATE is_active = TRUE, artifact_path = VALUES(artifact_path)
"""), {"v": version, "p": str(artifact_path).replace('\\', '/'), "t": datetime.now()})
db.commit()
db.close()
print("Model trained and registered as ACTIVE!")
