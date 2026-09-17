"""경로 소요시간 모델 온라인 추론과 fallback 검증."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from backend.src.services import route_eta_model as eta_module
from backend.src.services.route_eta_model import (
    apply_model_ranking,
    eligibility,
    feature_frame,
    load_route_model,
    predict_route_etas,
)

NOW = datetime(2026, 9, 17, 18, 0)


def candidate(route_id, duration, distance=5000.0):
    return SimpleNamespace(id=route_id, duration_sec=duration, distance_m=distance,
                           steps=[SimpleNamespace(name="강남대로", duration_sec=duration, distance_m=distance)])


def result(route_id, link_match_ratio=0.9, matches=None):
    return {"id": route_id, "ai": False, "score": 900.0, "link_match_ratio": link_match_ratio,
            "direction_match_ratio": 1.0, "link_match_details": matches or [
                {"index": 0, "total_m": 5000, "matched_m": 5000, "opposite_m": 0, "unmatched_m": 0,
                 "links": [{"link_id": "L1", "length_m": 5000}]}]}


class FakeModel:
    def __init__(self, values):
        self.values = values

    def predict(self, frame):
        assert len(frame) == len(self.values)
        return self.values


def bundle(values):
    return {"model": FakeModel(values), "feature_columns": ["osrm_duration_sec", "speed_lag_kmh", "speed_lag_coverage",
                                                            "active_incident_count", "departure_hour"], "version": "test_v1"}


def test_eligibility_requires_link_match_and_speed_coverage():
    assert eligibility(0.9, 0.8) == (True, [])
    ok, reasons = eligibility(0.3, 0.8)
    assert not ok and "링크 매칭률" in reasons[0]
    ok, reasons = eligibility(0.9, 0.1)
    assert not ok and "속도 관측" in reasons[0]
    assert eligibility(None, None)[0] is False


def test_feature_frame_zero_fills_counts_and_keeps_nan_for_speed():
    frame = feature_frame([{"osrm_duration_sec": 600}], ["osrm_duration_sec", "speed_lag_kmh", "active_incident_count"])
    assert list(frame.columns) == ["osrm_duration_sec", "speed_lag_kmh", "active_incident_count"]
    assert pd.isna(frame["speed_lag_kmh"].iloc[0]) and frame["active_incident_count"].iloc[0] == 0.0


def _patched_loaders(speed_kmh=30.0):
    observations = {"L1": [{"measured_at": NOW - timedelta(minutes=5), "speed_kmh": speed_kmh,
                            "travel_time_sec": None, "length_m": 5000}]} if speed_kmh else {}
    return [
        patch.object(eta_module, "load_link_observations", return_value=observations),
        patch.object(eta_module, "load_spot_links", return_value={}),
        patch.object(eta_module, "load_volume_lag", return_value={}),
        patch.object(eta_module, "load_active_incidents_by_link", return_value={}),
        patch.object(eta_module, "incident_data_age_sec", return_value=60),
        patch.object(eta_module, "load_weather_before", return_value={
            "weather_temperature_c": 20.0, "weather_rainfall_mm": 0.0, "weather_humidity_pct": 50.0,
            "weather_age_hours": 5.0, "weather_observed_at": NOW - timedelta(hours=5)}),
    ]


def test_predict_route_etas_uses_shared_features_and_reports_quality():
    patches = _patched_loaders()
    for p in patches:
        p.start()
    try:
        eta = predict_route_etas(MagicMock(), [candidate("A", 600), candidate("B", 700)],
                                 [result("A"), result("B")], NOW, NOW, bundle=bundle([1500.0, 1400.0]))
    finally:
        for p in patches:
            p.stop()
    assert eta["model_version"] == "test_v1"
    a, b = eta["routes"]["A"], eta["routes"]["B"]
    assert a["predicted_duration_sec"] == 1500.0 and b["predicted_duration_sec"] == 1400.0
    assert a["eligible"] and b["eligible"]
    assert a["speed_lag_coverage"] == 1.0 and a["speed_lag_age_min"] == 5.0 and a["speed_lag_kmh"] == 30.0
    assert a["incident_data_age_sec"] == 60


def test_predict_route_etas_marks_ineligible_without_speed_observations():
    patches = _patched_loaders(speed_kmh=None)
    for p in patches:
        p.start()
    try:
        eta = predict_route_etas(MagicMock(), [candidate("A", 600)], [result("A")], NOW, NOW, bundle=bundle([1500.0]))
    finally:
        for p in patches:
            p.stop()
    entry = eta["routes"]["A"]
    assert entry["eligible"] is False and any("속도 관측" in r for r in entry["reasons"])
    assert entry["predicted_duration_sec"] == 1500.0  # 값은 있지만 apply_model_ranking이 노출하지 않음


def test_predict_route_etas_returns_none_when_model_missing_or_inference_fails(tmp_path):
    assert load_route_model(tmp_path) is None
    with patch.object(eta_module, "load_route_model", return_value=None):
        assert predict_route_etas(MagicMock(), [candidate("A", 600)], [result("A")], NOW, NOW) is None
    # 조회 중 예외가 나도 추천 자체를 막지 않고 None을 돌려줍니다.
    with patch.object(eta_module, "load_link_observations", side_effect=RuntimeError("db down")):
        assert predict_route_etas(MagicMock(), [candidate("A", 600)], [result("A")], NOW, NOW, bundle=bundle([1.0])) is None


def test_apply_model_ranking_overrides_ai_only_when_all_candidates_eligible():
    results = [result("A"), result("B")]
    results[0]["ai"] = True  # 휴리스틱이 고른 A
    eta = {"model_version": "test_v1", "routes": {
        "A": {"eligible": True, "predicted_duration_sec": 1500.0, "reasons": [], "speed_lag_coverage": 0.9},
        "B": {"eligible": True, "predicted_duration_sec": 1400.0, "reasons": [], "speed_lag_coverage": 0.8},
    }}
    basis, applied = apply_model_ranking(results, eta)
    assert basis == "route_model" and applied
    assert [r["ai"] for r in results] == [False, True]  # 모델은 B를 선택
    assert results[0]["predicted_duration_sec"] == 1500.0 and results[0]["eta_source"] == "model"
    assert results[0]["eta_quality"]["speed_lag_coverage"] == 0.9


def test_apply_model_ranking_keeps_heuristic_when_any_candidate_ineligible():
    results = [result("A"), result("B")]
    results[0]["ai"] = True
    eta = {"model_version": "test_v1", "routes": {
        "A": {"eligible": True, "predicted_duration_sec": 1500.0, "reasons": []},
        "B": {"eligible": False, "predicted_duration_sec": 1400.0, "reasons": ["링크 매칭률 30% < 50%"]},
    }}
    basis, applied = apply_model_ranking(results, eta)
    assert basis == "heuristic_score" and not applied
    assert [r["ai"] for r in results] == [True, False]  # 휴리스틱 선택 유지
    assert results[0]["predicted_duration_sec"] == 1500.0 and results[0]["eta_source"] == "model"
    assert results[1]["predicted_duration_sec"] is None and results[1]["eta_source"] == "osrm"
    assert results[1]["eta_reasons"] == ["링크 매칭률 30% < 50%"]


def test_apply_model_ranking_without_eta_marks_all_as_osrm():
    results = [result("A")]
    basis, applied = apply_model_ranking(results, None)
    assert basis == "heuristic_score" and not applied
    assert results[0]["eta_source"] == "osrm" and results[0]["predicted_duration_sec"] is None
