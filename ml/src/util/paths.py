"""ML 프로젝트의 공통 경로 정의."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ML_ROOT = PROJECT_ROOT / "ml"
DATA_ROOT = PROJECT_ROOT / "data"

# ─── 교통량 예측 모델 경로 (기존 유지) ───────────────────────────────────────
TRAINING_DATASET = DATA_ROOT / "processed" / "traffic_training_dataset.csv"
ARTIFACTS_DIR = ML_ROOT / "artifacts"
REPORTS_DIR = ARTIFACTS_DIR / "reports"
ML_MODELS_DIR = ARTIFACTS_DIR / "ml_models"
LEADERBOARD_PATH = REPORTS_DIR / "leaderboard.csv"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ML_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 경로 소요시간 예측 모델 경로 ────────────────────────────────────────────
ROUTE_TRAINING_DATASET = DATA_ROOT / "processed" / "route_training_dataset.csv"
ROUTE_MODELS_DIR = ARTIFACTS_DIR / "route_models"
ROUTE_LEADERBOARD_PATH = REPORTS_DIR / "route_leaderboard.csv"

ROUTE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
