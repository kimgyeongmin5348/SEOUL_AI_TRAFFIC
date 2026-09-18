"""모델 학습과 추론에서 공유하는 기본 설정."""

# ─── 교통량 예측 모델 설정 (기존 유지) ──────────────────────────────────────
RANDOM_STATE = 42
TARGET_COLUMN = "target_volume"
TIME_SPLIT_RATIO = 0.8
BASELINE_N_ESTIMATORS = 200
BASELINE_LEARNING_RATE = 0.05
BASELINE_SUBSAMPLE = 0.8
BASELINE_COLSAMPLE_BYTREE = 0.8

# ─── 경로 소요시간 예측 모델 설정 ────────────────────────────────────────────
ROUTE_TARGET_COLUMN = "actual_duration_sec"
ROUTE_TIME_SPLIT_RATIO = 0.7  # 시간순 holdout 비율

# 피처 35개 — 모두 departure_at 이전에 수집된 관측값만 사용 (누수 없음)
ROUTE_FEATURE_COLUMNS = [
    # 경로 기본 정보
    "route_distance_m", "osrm_duration_sec", "segment_count",
    # 링크 매칭 품질
    "link_match_ratio", "direction_match_ratio", "opposite_direction_ratio",
    # 속도 피처
    "speed_lag_kmh", "speed_lag_min_kmh", "speed_lag_travel_time_sec",
    "speed_lag_coverage", "speed_lag_age_min", "speed_data_available",
    # 교통량 피처
    "volume_lag_vph_mean", "volume_lag_vph_max", "volume_lag_coverage", "volume_lag_age_hours",
    # 돌발상황 피처
    "active_incident_count", "accident_count", "construction_count",
    "control_count", "breakdown_count",
    "control_length_m", "blocked_length_m",
    "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio", "incident_data_age_sec",
    # 기상 피처
    "weather_temperature_c", "weather_rainfall_mm", "weather_humidity_pct", "weather_age_hours",
    # 시간 피처
    "departure_hour", "weekday", "is_weekend",
]

# 결측을 0으로 채워도 의미가 유지되는 컬럼(건수·비율·길이)
# 속도·교통량·기상 결측은 NaN 유지하여 모델이 구분하게 함
ROUTE_ZERO_FILL_COLUMNS = [
    "direction_match_ratio", "opposite_direction_ratio",
    "speed_lag_coverage", "speed_data_available",
    "volume_lag_coverage",
    "active_incident_count", "accident_count", "construction_count",
    "control_count", "breakdown_count",
    "control_length_m", "blocked_length_m",
    "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio",
]

# XGBoost 경로 모델 하이퍼파라미터
ROUTE_XGB_PARAMS = {
    "objective": "reg:squarederror",
    "n_estimators": 500,
    "learning_rate": 0.03,
    "max_depth": 5,
    "subsample": 0.85,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "tree_method": "hist",
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
}

# LightGBM 경로 모델 하이퍼파라미터
ROUTE_LGBM_PARAMS = {
    "objective": "regression",
    "n_estimators": 500,
    "learning_rate": 0.03,
    "num_leaves": 63,
    "subsample": 0.85,
    "colsample_bytree": 0.8,
    "min_child_samples": 10,
    "random_state": RANDOM_STATE,
    "n_jobs": -1,
    "verbose": -1,
}
