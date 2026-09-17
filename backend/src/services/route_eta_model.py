"""경로 소요시간 모델(route_xgb_duration_v1)로 후보별 ETA를 온라인 예측합니다.

- 피처는 학습 데이터셋과 같은 함수(`candidate_features`)로 만들어 학습·추론 불일치를 막습니다.
- 링크 매칭률·속도 관측 커버리지가 기준 미만인 후보는 예측을 내지 않고, 후보 중 하나라도
  자격 미달이면 추천 순위는 기존 휴리스틱 점수로 되돌립니다(정의서 §8 단계 4 fallback).
- 모델 파일이 없거나 예측 중 오류가 나면 None을 돌려주고 추천은 기존 방식대로 진행됩니다.
"""

import logging
import math
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from backend.src.services.route_duration_reconstruction import load_link_observations, matched_link_ids
from backend.src.services.route_training_dataset import (
    FEATURE_LAG_WINDOW_MIN,
    candidate_features,
    incident_data_age_sec,
    load_active_incidents_by_link,
    load_spot_links,
    load_volume_lag,
    load_weather_before,
    route_total_m,
    weather_features,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ROUTE_MODEL_DIR = ROOT / "ml" / "artifacts" / "route_models"
MODEL_VERSION = "route_xgb_duration_v1"
# 이 기준 미만이면 모델 ETA를 내지 않습니다. 학습 데이터셋의 link_match_ratio 10분위가 0.69였습니다.
MIN_LINK_MATCH_RATIO = 0.5
MIN_SPEED_LAG_COVERAGE = 0.3
# 학습 시 결측을 0으로 채운 컬럼(ml/src/models/route_duration_model.py와 동일해야 합니다).
ZERO_FILL_COLUMNS = [
    "direction_match_ratio", "opposite_direction_ratio", "speed_lag_coverage", "volume_lag_coverage", "speed_data_available",
    "active_incident_count", "accident_count", "construction_count", "control_count", "breakdown_count",
    "control_length_m", "blocked_length_m", "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio",
]


@lru_cache(maxsize=2)
def _load_bundle(path, modified):
    return joblib.load(path)


def load_route_model(directory=ROUTE_MODEL_DIR):
    """저장된 경로 모델 번들 {model, feature_columns, version}. 파일이 없으면 None."""
    path = directory / f"{MODEL_VERSION}.joblib"
    if not path.exists():
        return None
    bundle = _load_bundle(str(path), path.stat().st_mtime_ns)
    return {"model": bundle["model"], "feature_columns": list(bundle["feature_columns"]), "version": MODEL_VERSION}


def eligibility(link_match_ratio, speed_lag_coverage):
    """모델 ETA를 낼 자격과 미달 사유."""
    reasons = []
    if (link_match_ratio or 0.0) < MIN_LINK_MATCH_RATIO:
        reasons.append(f"링크 매칭률 {round((link_match_ratio or 0.0) * 100)}% < {round(MIN_LINK_MATCH_RATIO * 100)}%")
    if (speed_lag_coverage or 0.0) < MIN_SPEED_LAG_COVERAGE:
        reasons.append(f"속도 관측 커버리지 {round((speed_lag_coverage or 0.0) * 100)}% < {round(MIN_SPEED_LAG_COVERAGE * 100)}%")
    return not reasons, reasons


def feature_frame(rows, feature_columns):
    frame = pd.DataFrame(rows)
    for column in feature_columns:
        if column not in frame.columns:
            frame[column] = float("nan")
    for column in ZERO_FILL_COLUMNS:
        if column in frame.columns:
            frame[column] = frame[column].fillna(0.0)
    return frame[feature_columns]


def predict_route_etas(db, candidates, results, observation_at, departure_at, weather_row=None, bundle=None):
    """후보별 모델 ETA. 반환: {"model_version", "routes": {route_id: {...}}} 또는 사용 불가 시 None.

    observation_at: 관측 기준 시각(지금). departure_at: 출발 예정 시각(요일·시각 피처).
    results: rank_candidates 결과(링크 매칭 상세·비율 포함).
    """
    bundle = bundle or load_route_model()
    if bundle is None:
        return None
    try:
        matches_by_id = {r["id"]: r.get("link_match_details") or [] for r in results}
        link_ids = set().union(*(matched_link_ids(m) for m in matches_by_id.values())) if matches_by_id else set()
        lag_window = timedelta(minutes=FEATURE_LAG_WINDOW_MIN)
        by_link = load_link_observations(db, link_ids, observation_at - lag_window, observation_at)
        volumes = load_volume_lag(db, link_ids, load_spot_links(db), observation_at)
        incidents = load_active_incidents_by_link(db, link_ids, observation_at)
        incident_age = incident_data_age_sec(db, observation_at)
        weather = weather_features(weather_row, departure_at) if weather_row else load_weather_before(db, departure_at)

        rows, info = [], {}
        by_id = {r["id"]: r for r in results}
        for candidate in candidates:
            result = by_id[candidate.id]
            matches = matches_by_id[candidate.id]
            total_m = route_total_m({"steps": candidate.steps}, matches)
            features = candidate_features(matches, by_link, volumes, incidents, weather, observation_at,
                                          candidate.duration_sec, total_m, lag_window, incident_age)
            rows.append({
                **features,
                "route_distance_m": candidate.distance_m,
                "osrm_duration_sec": candidate.duration_sec,
                "segment_count": len(candidate.steps),
                "link_match_ratio": result.get("link_match_ratio"),
                "direction_match_ratio": result.get("direction_match_ratio"),
                "opposite_direction_ratio": _opposite_ratio(matches, total_m),
                "departure_hour": departure_at.hour,
                "weekday": departure_at.weekday(),
                "is_weekend": int(departure_at.weekday() >= 5),
            })
            eligible, reasons = eligibility(result.get("link_match_ratio"), features.get("speed_lag_coverage"))
            info[candidate.id] = {
                "eligible": eligible, "reasons": reasons,
                "speed_lag_coverage": features.get("speed_lag_coverage"),
                "speed_lag_age_min": features.get("speed_lag_age_min"),
                "speed_lag_kmh": features.get("speed_lag_kmh"),
                "volume_lag_coverage": features.get("volume_lag_coverage"),
                "active_incident_count": features.get("active_incident_count"),
                "control_length_m": features.get("control_length_m"),
                "incident_data_age_sec": incident_age,
            }
        predictions = bundle["model"].predict(feature_frame(rows, bundle["feature_columns"]))
        for candidate, value in zip(candidates, predictions, strict=True):
            value = float(value)
            entry = info[candidate.id]
            if not math.isfinite(value) or value <= 0:
                entry["eligible"] = False
                entry["reasons"].append("모델 예측값이 유효하지 않음")
                entry["predicted_duration_sec"] = None
            else:
                entry["predicted_duration_sec"] = round(value, 1)
        return {"model_version": bundle["version"], "routes": info}
    except Exception:
        # 모델 경로의 어떤 실패도 추천 자체를 막지 않습니다. 호출부는 휴리스틱으로 진행합니다.
        logger.warning("Route ETA model inference failed; falling back to heuristic ranking", exc_info=True)
        return None


def _opposite_ratio(matches, total_m):
    opposite = sum(float(m.get("opposite_m") or 0.0) for m in matches)
    return round(opposite / total_m, 3) if total_m else 0.0


def apply_model_ranking(results, eta):
    """모델 ETA를 결과에 붙이고, 모든 후보가 자격을 갖추면 예측 ETA 최소 후보를 AI 추천으로 바꿉니다.

    반환: (eta_basis, model_ranking_applied). eta_basis는 "route_model" 또는 "heuristic_score".
    """
    if not eta:
        for route in results:
            route.update(predicted_duration_sec=None, eta_source="osrm", eta_reasons=["경로 모델 사용 불가"], eta_quality=None)
        return "heuristic_score", False
    all_eligible = True
    for route in results:
        entry = eta["routes"].get(route["id"], {})
        eligible = bool(entry.get("eligible")) and entry.get("predicted_duration_sec") is not None
        all_eligible &= eligible
        route.update(
            predicted_duration_sec=entry.get("predicted_duration_sec") if eligible else None,
            eta_source="model" if eligible else "osrm",
            eta_reasons=entry.get("reasons", []),
            eta_quality={k: entry.get(k) for k in ("speed_lag_coverage", "speed_lag_age_min", "speed_lag_kmh",
                                                  "volume_lag_coverage", "active_incident_count",
                                                  "control_length_m", "incident_data_age_sec")},
        )
    if not all_eligible or not results:
        return "heuristic_score", False
    # 후보 간 비교는 같은 기준이어야 하므로 전부 자격이 있을 때만 모델 순위로 바꿉니다.
    for route in results:
        route["ai"] = False
    min(results, key=lambda r: r["predicted_duration_sec"])["ai"] = True
    return "route_model", True
