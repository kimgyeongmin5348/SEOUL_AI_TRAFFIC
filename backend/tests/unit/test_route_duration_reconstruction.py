"""경로 후보 actual_duration_sec 재구성 검증."""
from datetime import datetime, timedelta

import pytest

from backend.src.services.route_duration_reconstruction import (
    QUALITY_UNUSABLE,
    portion_seconds,
    quality_grade,
    reconstruct_candidate_duration,
    select_trip_observations,
)


def test_portion_seconds_scales_by_speed_or_link_travel_time_ratio():
    # 36km/h = 10m/s → 500m는 50초
    assert portion_seconds(500, {"speed_kmh": 36.0}) == pytest.approx(50)
    # 속도가 없으면 링크 통행시간을 링크 길이로 나눈 비율을 씁니다: 1000m에 100초 → 500m는 50초
    assert portion_seconds(500, {"speed_kmh": None, "travel_time_sec": 100.0, "length_m": 1000.0}) == pytest.approx(50)
    assert portion_seconds(500, {"speed_kmh": 0, "travel_time_sec": None, "length_m": None}) is None


def test_reconstruct_scales_observed_portion_and_keeps_osrm_for_the_rest():
    # 2,000m step 중 링크 L1에 1,200m, L2에 400m가 배분되고 400m는 미매칭.
    steps = [{"name": "강남대로", "duration_sec": 100, "distance_m": 2000}]
    matches = [{"index": 0, "total_m": 2000, "matched_m": 1600, "opposite_m": 0, "unmatched_m": 400,
                "links": [{"link_id": "L1", "length_m": 1200}, {"link_id": "L2", "length_m": 400}]}]
    observations = {"L1": {"speed_kmh": 36.0}}  # L2는 관측 없음
    result = reconstruct_candidate_duration(steps, matches, observations)
    # L1 1,200m @ 10m/s = 120초, 나머지 800m는 OSRM 100초의 40% = 40초
    assert result["duration_sec"] == pytest.approx(160)
    assert result["observed_m"] == 1200 and result["total_m"] == 2000 and result["observed_steps"] == 1


def test_reconstruct_does_not_use_link_travel_time_as_step_time():
    # 딥시크 버그 재현 방지: 300m 링크의 통행시간(30초)을 2,000m step 전체 시간으로 쓰면 안 됩니다.
    steps = [{"name": "녹사평대로", "duration_sec": 126, "distance_m": 2000}]
    matches = [{"index": 0, "total_m": 2000, "links": [{"link_id": "L", "length_m": 300}]}]
    result = reconstruct_candidate_duration(steps, matches, {"L": {"speed_kmh": None, "travel_time_sec": 30, "length_m": 300}})
    # 300m 구간 30초 + 나머지 1,700m는 OSRM 비례 107.1초
    assert result["duration_sec"] == pytest.approx(30 + 126 * 0.85)
    assert result["duration_sec"] != 30


def test_reconstruct_keeps_osrm_time_when_no_link_match():
    steps = [{"name": "강남대로", "duration_sec": 100, "distance_m": 1000}]
    matches = [{"index": 0, "links": [], "total_m": 1000, "direction_match": None}]
    result = reconstruct_candidate_duration(steps, matches, {})
    assert result["duration_sec"] == 100.0 and result["observed_m"] == 0 and result["total_m"] == 1000
    assert reconstruct_candidate_duration([], [], {})["duration_sec"] == 0.0


def test_quality_grade_by_observed_length_ratio():
    assert quality_grade(1000, 900) == "high"
    assert quality_grade(1000, 600) == "medium"
    assert quality_grade(1000, 350) == "low"
    assert quality_grade(1000, 100) == QUALITY_UNUSABLE
    assert quality_grade(0, 0) == QUALITY_UNUSABLE


def test_select_trip_observations_uses_trip_midpoint_within_window():
    departure = datetime(2026, 9, 13, 18, 0)
    by_link = {"L": [
        {"measured_at": departure - timedelta(minutes=50), "speed_kmh": 40.0},
        {"measured_at": departure + timedelta(minutes=10), "speed_kmh": 20.0},  # 주행 중간(출발+10분)에 가장 가까움
    ], "FAR": [{"measured_at": departure + timedelta(hours=3), "speed_kmh": 50.0}]}
    selected = select_trip_observations(by_link, {"L", "FAR"}, departure, 1200, timedelta(minutes=60))
    assert selected["L"]["speed_kmh"] == 20.0
    assert "FAR" not in selected
