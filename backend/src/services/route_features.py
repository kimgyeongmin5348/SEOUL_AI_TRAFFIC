"""경로 소요시간 모델의 피처 정의.

학습 파이프라인(ml/src, 저장소에서 제거됨)과 추론이 공유하던 상수를 backend 안으로 옮겼습니다.
배포 이미지에는 backend/ 와 ml/artifacts/ 만 복사되므로, 추론 코드는 ml/src 를 import 하면 안 됩니다.
저장된 모델(ml/artifacts/route_models/*.joblib)의 feature_columns 와 순서·이름이 같아야 합니다.
"""

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
