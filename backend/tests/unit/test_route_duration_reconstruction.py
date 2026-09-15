"""경로 후보 actual_duration_sec 재구성 검증."""
from backend.src.services.route_duration_reconstruction import (
    quality_grade,
    reconstruct_candidate_duration,
)


def test_reconstruct_uses_observed_travel_time_for_matched_steps():
    # 링크가 매칭된 step은 관측 통행시간으로, 미매칭 step은 OSRM 시간으로 합산합니다.
    steps = [
        {"name": "강남대로", "duration_sec": 100, "distance_m": 1000},
        {"name": "테헤란로", "duration_sec": 200, "distance_m": 2000},
    ]
    matches = [
        {"index": 0, "link_id": "L1", "direction_match": True},
        {"index": 1, "link_id": "L2", "direction_match": True},
    ]
    travel_times = {"L1": 150.0}
    duration, observed, matched = reconstruct_candidate_duration(steps, matches, travel_times)
    # L1 관측 150 + L2 미관측 OSRM 200
    assert duration == 350.0
    assert observed == 1
    assert matched == 2


def test_reconstruct_keeps_osrm_time_when_no_link_match():
    steps = [{"name": "강남대로", "duration_sec": 100, "distance_m": 1000}]
    matches = [{"index": 0, "link_id": None, "direction_match": None}]
    duration, observed, matched = reconstruct_candidate_duration(steps, matches, {})
    assert duration == 100.0
    assert observed == 0
    assert matched == 0


def test_reconstruct_handles_missing_steps_json():
    duration, observed, matched = reconstruct_candidate_duration([], [], {})
    assert duration == 0.0
    assert observed == 0
    assert matched == 0


def test_quality_grade_thresholds():
    assert quality_grade(10, 9, 9) == "high"
    assert quality_grade(10, 6, 4) == "medium"
    assert quality_grade(10, 6, 1) == "low"
    assert quality_grade(10, 0, 0) == "low"
    assert quality_grade(0, 0, 0) == "low"