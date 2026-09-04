"""ML 프로젝트의 공통 경로 정의."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ML_ROOT = PROJECT_ROOT / "ml"
DATA_ROOT = PROJECT_ROOT / "data"
TRAINING_DATASET = DATA_ROOT / "processed" / "traffic_training_dataset.csv"
ARTIFACTS_DIR = ML_ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
