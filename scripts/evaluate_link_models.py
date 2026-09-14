"""Evaluate link-level speed and travel-time models without changing production artifacts."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from xgboost import XGBRegressor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.util.config import (
    BASELINE_COLSAMPLE_BYTREE,
    BASELINE_LEARNING_RATE,
    BASELINE_N_ESTIMATORS,
    BASELINE_SUBSAMPLE,
    RANDOM_STATE,
)
from ml.src.util.train import evaluate


EXCLUDED = {
    "target_speed_kmh", "target_travel_time_sec", "target_datetime",
    "datetime", "link_id", "road_name", "start_node_name", "end_node_name",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate link-level regression targets")
    parser.add_argument("--input", type=Path, default=Path("data/processed/link_training_dataset.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    frame = frame.sort_values("datetime").reset_index(drop=True)
    cutoff_index = max(1, int(len(frame) * 0.8))
    cutoff = frame.loc[cutoff_index, "datetime"]
    # 시간순 분할로 미래 링크 관측이 학습에 섞이지 않게 합니다.
    train = frame[frame["datetime"] < cutoff]
    test = frame[frame["datetime"] >= cutoff]
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
    results = {}
    for target in ("target_speed_kmh", "target_travel_time_sec"):
        features = [
            column for column in frame.columns
            if column not in EXCLUDED and column != target
            and pd.api.types.is_numeric_dtype(frame[column])
        ]
        model = XGBRegressor(**params)
        model.fit(train[features], train[target])
        results[target] = {
            "features": features,
            "metrics": evaluate(model, test, features, target),
        }
    print(json.dumps({
        "dataset": str(args.input),
        "rows": len(frame),
        "links": int(frame["link_id"].nunique()),
        "cutoff": str(cutoff),
        "train_rows": len(train),
        "test_rows": len(test),
        "targets": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()