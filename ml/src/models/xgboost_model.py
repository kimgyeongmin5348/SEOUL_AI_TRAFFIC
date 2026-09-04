"""XGBoost 기본 회귀 모델 학습 진입점."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from xgboost import XGBRegressor


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
from ml.src.util.paths import ARTIFACTS_DIR, TRAINING_DATASET
from ml.src.util.train import evaluate, load_full_dataset, load_time_split, register_model_version, save_artifact, save_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the XGBoost baseline")
    parser.add_argument("--input", type=Path, default=TRAINING_DATASET)
    parser.add_argument("--nrows", type=int, default=None)
    parser.add_argument("--no-db", action="store_true", help="DB model registry 저장 생략")
    args = parser.parse_args()

    train, validation, features, cutoff = load_time_split(
        args.input, target=TARGET_COLUMN, nrows=args.nrows
    )
    params = {
        "objective": "reg:squarederror",
        "n_estimators": BASELINE_N_ESTIMATORS,
        "learning_rate": BASELINE_LEARNING_RATE,
        "max_depth": 6,
        "subsample": BASELINE_SUBSAMPLE,
        "colsample_bytree": BASELINE_COLSAMPLE_BYTREE,
        "tree_method": "hist",
        "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }
    validation_model = XGBRegressor(**params)
    validation_model.fit(train[features], train[TARGET_COLUMN])
    metrics = evaluate(validation_model, validation, features, TARGET_COLUMN)
    full_df, full_features = load_full_dataset(args.input, target=TARGET_COLUMN, nrows=args.nrows)
    model = XGBRegressor(**params)
    model.fit(full_df[full_features], full_df[TARGET_COLUMN])

    version = "traffic_xgb_baseline_v1"
    artifact = ARTIFACTS_DIR / "xgboost" / f"{version}.joblib"
    metrics_path = ARTIFACTS_DIR / "xgboost" / f"{version}_metrics.json"
    result = {
        "model_version": version,
        "algorithm": "XGBoost",
        "split": "full_historical_train_with_time_validation",
        "cutoff_time": str(cutoff),
        "train_rows": len(full_df),
        "validation_rows": len(validation),
        "feature_columns": full_features,
        **metrics,
    }
    save_artifact(model, artifact)
    save_metrics(metrics_path, result)
    if not args.no_db:
        register_model_version(
            model_version=version,
            algorithm="XGBoost",
            hyperparameters=params,
            metrics=metrics,
            artifact_path=artifact,
            trained_at=datetime.now(),
        )
    print(result)


if __name__ == "__main__":
    main()
