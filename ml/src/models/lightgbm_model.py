"""LightGBM 기본 회귀 모델 학습 진입점."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from lightgbm import LGBMRegressor


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.util.config import (
    BASELINE_COLSAMPLE_BYTREE,
    BASELINE_LEARNING_RATE,
    BASELINE_N_ESTIMATORS,
    BASELINE_SUBSAMPLE,
    RANDOM_STATE,
    TARGET_COLUMN,
)
from ml.src.util.paths import ML_MODELS_DIR, REPORTS_DIR, TRAINING_DATASET
from ml.src.util.train import evaluate, load_full_dataset, load_time_split, save_if_better


def train_model(*, input_path: Path | None = None, nrows: int | None = None, no_db: bool = False) -> dict:
    dataset_path = input_path or TRAINING_DATASET
    parser = argparse.ArgumentParser(description="Train the LightGBM baseline")
    train, validation, features, cutoff = load_time_split(
        dataset_path, target=TARGET_COLUMN, nrows=nrows
    )
    params = {
        "objective": "regression",
        "n_estimators": BASELINE_N_ESTIMATORS,
        "learning_rate": BASELINE_LEARNING_RATE,
        "num_leaves": 31,
        "subsample": BASELINE_SUBSAMPLE,
        "colsample_bytree": BASELINE_COLSAMPLE_BYTREE,
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }
    validation_model = LGBMRegressor(**params)
    validation_model.fit(train[features], train[TARGET_COLUMN])
    metrics = evaluate(validation_model, validation, features, TARGET_COLUMN)
    full_df, full_features = load_full_dataset(dataset_path, target=TARGET_COLUMN, nrows=nrows)
    model = LGBMRegressor(**params)
    model.fit(full_df[full_features], full_df[TARGET_COLUMN])

    version = "traffic_lgbm_baseline_v1"
    artifact = ML_MODELS_DIR / f"{version}.joblib"
    result = {
        "model_version": version,
        "algorithm": "LightGBM",
        "split": "full_historical_train_with_time_validation",
        "cutoff_time": str(cutoff),
        "train_rows": len(full_df),
        "validation_rows": len(validation),
        "feature_columns": full_features,
        "hyperparameters": params,
        **metrics,
    }
    report_path = REPORTS_DIR / f"{version}_report.csv"
    accepted = save_if_better(
        model=model,
        artifact_path=artifact,
        report_path=report_path,
        report=result,
        no_db=no_db,
    )
    result["accepted"] = accepted
    print(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the LightGBM baseline")
    parser.add_argument("--input", type=Path, default=TRAINING_DATASET)
    parser.add_argument("--nrows", type=int, default=None)
    parser.add_argument("--no-db", action="store_true", help="DB model registry 저장 생략")
    args = parser.parse_args()
    train_model(input_path=args.input, nrows=args.nrows, no_db=args.no_db)
