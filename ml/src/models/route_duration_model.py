"""경로 후보의 actual_duration_sec 회귀 모델과 순위 평가를 학습합니다.

문제 정의서 §5.3·§7을 구현합니다. 경로 학습 데이터셋(route_training_dataset.csv)을
시간순으로 분할해 actual_duration_sec를 예측하고, 회귀 지표(MAE/RMSE/R²)와 함께
경로 추천 지표(Top-1, pairwise, regret)를 계산합니다.

원칙: 데이터가 너무 적으면 아티팩트를 자동 채택하지 않습니다. 최소 행 수를 넘기고
시간순 holdout에서 순위 지표가 산출될 때만 운영 아티팩트로 저장합니다.
"""

import json
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from backend.src.services.route_ranking_evaluation import (
    mean_regret,
    pairwise_ranking_accuracy,
    top1_accuracy,
)

# 모델 입력으로 쓰는 수치형 Feature. direction_match_ratio는 결측 시 0으로 채웁니다.
FEATURE_COLUMNS = [
    "route_distance_m",
    "osrm_duration_sec",
    "segment_count",
    "link_match_ratio",
    "direction_match_ratio",
    "departure_hour",
]
TARGET = "actual_duration_sec"
MODEL_VERSION = "route_xgb_duration_v1"
# 운영 아티팩트로 채택하기 위한 최소 학습 행 수(품질 등급 high/medium 권장).
DEFAULT_MIN_ROWS = 50


def prepare_dataset(frame):
    """CSV를 Feature 행렬과 시간순 정렬된 프레임으로 변환합니다."""
    frame = frame.copy()
    frame["departure_at"] = pd.to_datetime(frame["departure_at"])
    frame = frame.sort_values("departure_at").reset_index(drop=True)
    frame["departure_hour"] = frame["departure_at"].dt.hour
    frame["direction_match_ratio"] = frame["direction_match_ratio"].fillna(0.0)
    return frame


def time_split(frame, ratio=0.7):
    """시간순으로 train/holdout을 나눕니다."""
    split_index = max(1, int(len(frame) * ratio))
    if split_index >= len(frame):
        return frame, frame.iloc[0:0]
    cutoff = frame.loc[split_index, "departure_at"]
    train = frame[frame["departure_at"] < cutoff]
    test = frame[frame["departure_at"] >= cutoff]
    return train, test


def regression_metrics(y_true, y_pred):
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def requests_from_predictions(frame, predictions):
    """예측 통행시간을 비용 점수(낮을수록 우수)로 써서 요청 단위 순위 평가 입력을 만듭니다."""
    frame = frame.copy()
    frame["score"] = [float(value) for value in predictions]
    grouped = {}
    for row in frame.itertuples():
        grouped.setdefault(row.route_request_id, []).append({
            "route_id": row.route_id,
            "score": float(row.score),
            "actual_duration_sec": float(row.actual_duration_sec),
        })
    return [{"route_request_id": key, "candidates": value} for key, value in grouped.items()]


def ranking_metrics(requests):
    return {
        "top1_accuracy": top1_accuracy(requests),
        "pairwise_ranking_accuracy": pairwise_ranking_accuracy(requests),
        "mean_regret_sec": mean_regret(requests),
    }


def train_route_model(dataset_path: Path, artifacts_dir: Path, min_rows: int = DEFAULT_MIN_ROWS,
                      force: bool = False, ratio: float = 0.7):
    """경로 소요시간 모델을 학습하고 (성공 시) 아티팩트와 리포트를 저장합니다."""
    frame = prepare_dataset(pd.read_csv(dataset_path))
    if len(frame) < min_rows and not force:
        return {
            "status": "insufficient_data", "rows": len(frame), "min_rows": min_rows,
            "message": f"학습 행이 {min_rows}개 미만({len(frame)}개)이라 아티팩트를 채택하지 않았습니다. --force로 강제 학습할 수 있습니다.",
        }

    train, test = time_split(frame, ratio)
    if train.empty or test.empty:
        return {"status": "insufficient_data", "rows": len(frame), "message": "시간순 분할에 실패했습니다."}

    import xgboost as xgb

    model = xgb.XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9)
    model.fit(train[FEATURE_COLUMNS], train[TARGET])
    predictions = model.predict(test[FEATURE_COLUMNS])
    metrics = regression_metrics(test[TARGET].to_numpy(), predictions)
    ranking = ranking_metrics(requests_from_predictions(test, predictions))

    artifact_path = artifacts_dir / "ml_models" / f"{MODEL_VERSION}.joblib"
    report_path = artifacts_dir / "reports" / f"{MODEL_VERSION}_report.csv"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "target": TARGET}, artifact_path)
    report = {
        "model_version": MODEL_VERSION, "algorithm": "XGBoostRegressor",
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(frame), "train_rows": len(train), "holdout_rows": len(test),
        "feature_columns": json.dumps(FEATURE_COLUMNS, ensure_ascii=False),
        **metrics, **ranking,
    }
    pd.DataFrame([report]).to_csv(report_path, index=False, encoding="utf-8-sig")
    return {"status": "trained", "artifact": str(artifact_path), "report": str(report_path), **report}