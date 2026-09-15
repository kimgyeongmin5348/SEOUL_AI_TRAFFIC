"""경로 학습 데이터셋 생성 로직 검증."""
from datetime import datetime, timedelta

import pytest

from backend.src.services.route_training_dataset import (
    OsrmStep,
    assign_ranks,
    build_candidate_record,
    incident_features,
    match_candidate,
    parse_osrm_routes,
    speed_lag_features,
    write_csv,
)

LAT = 37.5


def _candidate(route_id, duration, steps, distance=1000.0):
    return {"route_id": route_id, "distance_m": distance, "duration_sec": duration,
            "coordinates": [], "steps": steps}


def _link(link_id, x0, x1, bearing=90.0):
    return {"link_id": link_id, "polyline": [(x0, LAT), (x1, LAT)], "bearing_deg": bearing, "length_m": abs(x1 - x0) * 88000}


def test_parse_osrm_routes_limits_to_three_and_reads_steps():
    payload = {"routes": [
        {"distance": 1000, "duration": 120, "geometry": {"coordinates": [[1, 2]]},
         "legs": [{"steps": [
             {"name": "강남대로", "duration": 60, "distance": 500,
              "geometry": {"coordinates": [[1, 2], [3, 4]]}},
         ]}]},
    ]}
    candidates = parse_osrm_routes(payload)
    assert len(candidates) == 1
    assert candidates[0]["route_id"] == "A"
    assert candidates[0]["distance_m"] == 1000.0
    assert candidates[0]["steps"][0].name == "강남대로"
    assert candidates[0]["steps"][0].coordinates == [[1, 2], [3, 4]]


def test_parse_osrm_routes_empty_payload():
    assert parse_osrm_routes({}) == []


def test_build_candidate_record_without_link_geometry_has_no_label():
    # 링크 기하가 없으면 관측을 쓸 수 없으므로 라벨을 만들지 않고 unusable로 남깁니다.
    step = OsrmStep(name="강남대로", duration_sec=100.0, distance_m=1000.0, coordinates=[[127.0, LAT], [127.01, LAT]])
    candidate = _candidate("A", 100.0, [step])
    record = build_candidate_record(candidate, match_candidate(candidate, {}), {})
    assert record.actual_duration_sec is None and record.actual_delay_sec is None
    assert record.link_match_ratio == 0.0 and record.quality == "unusable"


def test_build_candidate_record_scales_step_by_observed_link_speed():
    # 176m step 전체가 링크 L1에 매칭되고 36km/h 관측이면 17.6초, 품질 high.
    step = OsrmStep(name="강남대로", duration_sec=100.0, distance_m=176.0, coordinates=[[127.0, LAT], [127.002, LAT]])
    candidate = _candidate("A", 100.0, [step])
    matches = match_candidate(candidate, {"강남대로": [_link("L1", 127.0, 127.002)]})
    record = build_candidate_record(candidate, matches, {"L1": {"speed_kmh": 36.0}}, {"speed_lag_kmh": 30.0})
    assert record.actual_duration_sec == pytest.approx(17.6, abs=0.3)
    assert record.actual_delay_sec == pytest.approx(-82.4, abs=0.3)
    assert record.quality == "high" and record.link_match_ratio == 1.0
    assert record.direction_match_ratio == 1.0 and record.opposite_direction_ratio == 0.0
    assert record.features == {"speed_lag_kmh": 30.0}


def test_assign_ranks_skips_unusable_and_needs_two_labelled_candidates():
    a = type("C", (), {"actual_duration_sec": 200.0})()
    b = type("C", (), {"actual_duration_sec": 150.0})()
    c = type("C", (), {"actual_duration_sec": None})()
    assign_ranks([a, b, c])
    assert b.rank_actual == 1 and b.chosen_best is True
    assert a.rank_actual == 2 and a.chosen_best is False
    assert c.rank_actual is None and c.chosen_best is None
    assign_ranks([a, c])
    assert a.rank_actual is None and a.chosen_best is None


def test_speed_lag_features_use_only_observations_before_departure():
    departure = datetime(2026, 9, 13, 18, 0)
    matches = [{"total_m": 1000, "links": [{"link_id": "L1", "length_m": 600}, {"link_id": "L2", "length_m": 200}]}]
    by_link = {
        "L1": [{"measured_at": departure - timedelta(minutes=10), "speed_kmh": 30.0},
               {"measured_at": departure + timedelta(minutes=5), "speed_kmh": 10.0}],  # 출발 이후 → 사용 금지
        "L2": [{"measured_at": departure - timedelta(hours=3), "speed_kmh": 50.0}],   # 창 밖
    }
    features = speed_lag_features(matches, by_link, departure, timedelta(minutes=60))
    assert features == {"speed_lag_kmh": 30.0, "speed_lag_coverage": 0.6}


def test_incident_features_count_active_incidents_on_matched_links_by_category():
    matches = [{"links": [{"link_id": "L1", "length_m": 100}, {"link_id": "L2", "length_m": 100}]}]
    incidents = {
        "L1": [{"incident_id": "i1", "incident_type": "A01", "incident_detail_type": ""},
               {"incident_id": "i2", "incident_type": "A04", "incident_detail_type": ""}],
        "L2": [{"incident_id": "i2", "incident_type": "A04", "incident_detail_type": ""}],  # 같은 돌발 중복
        "L9": [{"incident_id": "i3", "incident_type": "A08", "incident_detail_type": ""}],  # 경로 밖
    }
    features = incident_features(matches, incidents)
    assert features["active_incident_count"] == 2
    assert features["accident_count"] == 1 and features["construction_count"] == 1
    assert features["control_count"] == 0 and features["breakdown_count"] == 0


def test_write_csv_writes_header_and_rows(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = write_csv(rows, tmp_path / "out.csv")
    text = path.read_text(encoding="utf-8-sig")
    assert "a,b" in text
    assert "1,x" in text and "2,y" in text


def test_write_csv_handles_empty_rows(tmp_path):
    path = write_csv([], tmp_path / "empty.csv")
    assert path.read_text(encoding="utf-8-sig") == ""
