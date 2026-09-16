"""경로 후보의 actual_duration_sec 회귀 모델과 순위 평가를 학습합니다.

문제 정의서 §5.3·§7을 구현합니다. 경로 학습 데이터셋(route_training_dataset.csv)을
시간순으로 분할해 actual_duration_sec를 예측하고, 회귀 지표(MAE/RMSE/R²)와 함께
경로 추천 지표(Top-1, pairwise, regret)를 계산합니다.

원칙
- 같은 holdout에서 OSRM 순서(osrm_duration_sec 오름차순) 베이스라인과 반드시 비교합니다.
  라벨의 미관측 구간이 OSRM 시간을 유지하므로 모델이 OSRM을 복제만 해도 지표가 좋아 보일 수 있습니다.
- 학습 행이 부족하거나 베이스라인을 이기지 못하면 아티팩트를 채택하지 않습니다.
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

# 모델 입력 Feature. 모두 출발 시각 이전 정보만으로 계산됩니다(정의서 §6, check_route_dataset.py로 검증).
FEATURE_COLUMNS = [
    "route_distance_m", "osrm_duration_sec", "segment_count",
    "link_match_ratio", "direction_match_ratio", "opposite_direction_ratio",
    "speed_lag_kmh", "speed_lag_min_kmh", "speed_lag_travel_time_sec", "speed_lag_coverage", "speed_lag_age_min",
    "speed_data_available",
    "volume_lag_vph_mean", "volume_lag_vph_max", "volume_lag_coverage", "volume_lag_age_hours",
    "active_incident_count", "accident_count", "construction_count", "control_count", "breakdown_count",
    "control_length_m", "blocked_length_m", "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio", "incident_data_age_sec",
    "weather_temperature_c", "weather_rainfall_mm", "weather_humidity_pct", "weather_age_hours",
    "departure_hour", "weekday", "is_weekend",
]
# 결측을 0으로 채워도 의미가 유지되는 컬럼(비율·건수·길이). 속도·교통량·기상 결측은 NaN으로 두어 모델이 구분합니다.
ZERO_FILL_COLUMNS = [
    "direction_match_ratio", "opposite_direction_ratio", "speed_lag_coverage", "volume_lag_coverage", "speed_data_available",
    "active_incident_count", "accident_count", "construction_count", "control_count", "breakdown_count",
    "control_length_m", "blocked_length_m", "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio",
]
TARGET = "actual_duration_sec"
MODEL_VERSION = "route_xgb_duration_v1"
# 운영 아티팩트로 채택하기 위한 최소 학습 행 수(라벨 있는 행 기준).
DEFAULT_MIN_ROWS = 50


def prepare_dataset(frame):
    """CSV를 시간순 정렬된 학습 프레임으로 변환합니다. 라벨 없는(unusable) 행은 제외합니다."""
    frame = frame.copy()
    frame["departure_at"] = pd.to_datetime(frame["departure_at"])
    frame = frame[frame[TARGET].notna()]
    frame = frame.sort_values(["departure_at", "route_request_id", "route_id"]).reset_index(drop=True)
    frame["departure_hour"] = frame["departure_at"].dt.hour
    frame["weekday"] = frame["departure_at"].dt.weekday
    frame["is_weekend"] = (frame["weekday"] >= 5).astype(int)
    for column in FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = float("nan")
    for column in ZERO_FILL_COLUMNS:
        frame[column] = frame[column].fillna(0.0)
    return frame


def time_split(frame, ratio=0.7):
    """시간순으로 train/holdout을 나눕니다. 같은 출발 시각(=같은 요청)은 한쪽에만 들어갑니다."""
    split_index = max(1, int(len(frame) * ratio))
    if split_index >= len(frame):
        return frame, frame.iloc[0:0]
    cutoff = frame.loc[split_index, "departure_at"]
    train = frame[frame["departure_at"] < cutoff]
    test = frame[frame["departure_at"] >= cutoff]
    return train, test


def od_split(frame, holdout_ratio=0.25, seed=42):
    """OD 쌍(출발지→목적지) 기준으로 train/holdout을 나눕니다. 학습에 없는 경로로의 일반화를 측정합니다."""
    pairs = sorted(frame[["origin_name", "destination_name"]].drop_duplicates().itertuples(index=False, name=None))
    if len(pairs) < 2:
        return frame, frame.iloc[0:0]
    import random
    shuffled = pairs[:]
    random.Random(seed).shuffle(shuffled)
    holdout = set(shuffled[:max(1, int(len(shuffled) * holdout_ratio))])
    mask = [(o, d) in holdout for o, d in zip(frame["origin_name"], frame["destination_name"])]
    mask = pd.Series(mask, index=frame.index)
    return frame[~mask], frame[mask]


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


def baseline_metrics(test):
    """OSRM 시간 그대로를 예측·점수로 쓴 베이스라인 지표."""
    osrm = test["osrm_duration_sec"].to_numpy(dtype=float)
    return {
        **{f"baseline_{k}": v for k, v in regression_metrics(test[TARGET].to_numpy(), osrm).items()},
        **{f"baseline_{k}": v for k, v in ranking_metrics(requests_from_predictions(test, osrm)).items()},
    }


def beats_baseline(metrics, baseline):
    """정의서 §7: 순위 지표와 regret가 함께 개선돼야 채택합니다."""
    top1, base_top1 = metrics.get("top1_accuracy"), baseline.get("baseline_top1_accuracy")
    regret, base_regret = metrics.get("mean_regret_sec"), baseline.get("baseline_mean_regret_sec")
    if top1 is None or base_top1 is None or regret is None or base_regret is None:
        return False
    return top1 >= base_top1 and regret <= base_regret and metrics["mae"] < baseline["baseline_mae"]


def fit_and_evaluate(train, test):
    """train으로 학습하고 test에서 모델·베이스라인 지표를 계산합니다."""
    import xgboost as xgb

    model = xgb.XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9)
    model.fit(train[FEATURE_COLUMNS], train[TARGET])
    predictions = model.predict(test[FEATURE_COLUMNS])
    metrics = {**regression_metrics(test[TARGET].to_numpy(), predictions),
               **ranking_metrics(requests_from_predictions(test, predictions))}
    return model, metrics, baseline_metrics(test)


def train_route_model(dataset_path: Path, artifacts_dir: Path, min_rows: int = DEFAULT_MIN_ROWS,
                      force: bool = False, ratio: float = 0.7):
    """경로 소요시간 모델을 학습하고, 베이스라인을 이기면 아티팩트와 리포트를 저장합니다.

    채택 기준은 정의서 §7의 시간순 holdout이며, OD holdout(학습에 없는 출발·목적지) 지표는
    일반화 참고값으로 함께 기록합니다.
    """
    frame = prepare_dataset(pd.read_csv(dataset_path))
    if len(frame) < min_rows and not force:
        return {
            "status": "insufficient_data", "rows": len(frame), "min_rows": min_rows,
            "message": f"라벨 있는 학습 행이 {min_rows}개 미만({len(frame)}개)이라 아티팩트를 채택하지 않았습니다. --force로 강제 학습할 수 있습니다.",
        }

    train, test = time_split(frame, ratio)
    if train.empty or test.empty:
        return {"status": "insufficient_data", "rows": len(frame), "message": "시간순 분할에 실패했습니다."}
    model, metrics, baseline = fit_and_evaluate(train, test)
    adopted = beats_baseline(metrics, baseline) or force

    od_report = {}
    od_train, od_test = od_split(frame)
    if not od_train.empty and not od_test.empty:
        _, od_metrics, od_baseline = fit_and_evaluate(od_train, od_test)
        od_report = {
            "od_holdout_pairs": int(od_test[["origin_name", "destination_name"]].drop_duplicates().shape[0]),
            "od_holdout_rows": len(od_test),
            **{f"od_{k}": v for k, v in od_metrics.items()},
            **{f"od_{k}": v for k, v in od_baseline.items()},
            "od_generalizes": beats_baseline(od_metrics, od_baseline),
        }

    report = {
        "model_version": MODEL_VERSION, "algorithm": "XGBoostRegressor",
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "rows": len(frame), "train_rows": len(train), "holdout_rows": len(test),
        "holdout_requests": test["route_request_id"].nunique(),
        "feature_columns": json.dumps(FEATURE_COLUMNS, ensure_ascii=False),
        **metrics, **baseline, **od_report, "adopted": adopted,
    }
    if not adopted:
        return {"status": "not_adopted", **report,
                "message": "시간순 holdout에서 OSRM 순서 베이스라인을 이기지 못해 아티팩트를 채택하지 않았습니다."}

    # ml_models/·reports/는 교통량 모델 leaderboard(best_saved_model)가 glob하므로 경로 모델은 따로 둡니다.
    artifact_path = artifacts_dir / "route_models" / f"{MODEL_VERSION}.joblib"
    report_path = artifacts_dir / "route_models" / f"{MODEL_VERSION}_report.csv"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    # 운영 아티팩트는 전체 시간순 train으로 학습한 모델입니다(OD 분할 모델은 평가 전용).
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "target": TARGET}, artifact_path)
    pd.DataFrame([report]).to_csv(report_path, index=False, encoding="utf-8-sig")
    return {"status": "trained", "artifact": str(artifact_path), "report": str(report_path), **report}
