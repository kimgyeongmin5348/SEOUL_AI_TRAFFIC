"""경로 학습 데이터셋 생성 로직 검증."""
from datetime import datetime

from backend.src.services.route_training_dataset import (
    OsrmStep,
    assign_ranks,
    build_candidate_record,
    parse_osrm_routes,
    write_csv,
)


def _candidate(route_id, duration, steps):
    return {"route_id": route_id, "distance_m": 1000.0, "duration_sec": duration,
            "coordinates": [], "steps": steps}


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


def test_build_candidate_record_without_link_geometry_keeps_osrm_time():
    # 크 기하가 없으면 관측을 쓰지 않고 OSRM 시간을 유지하며 품질은 low입니다.
    step = OsrmStep(name="강남대로", duration_sec=100.0, distance_m=1000.0, coordinates=[[0, 0], [0, 1]])
    record = build_candidate_record(_candidate("A", 100.0, [step]), {}, {})
    assert record.actual_duration_sec == 100.0
    assert record.actual_delay_sec == 0.0
    assert record.link_match_ratio == 0.0
    assert record.quality == "low"


def test_build_candidate_record_uses_matched_link_travel_time():
    # step 중간점이 링크 선분 위에 있어 map-match되고 관측 통행시간으로 대체됩니다.
    step = OsrmStep(name="강남대로", duration_sec=100.0, distance_m=1000.0,
                    coordinates=[[0.0, 0.0], [0.0, 0.001]])
    link_geometry = {"강남대로": [{
        "link_id": "L1",
        "segment": [(0.0, 0.0), (0.0, 0.001)],
        "bearing_deg": 0.0,
    }]}
    record = build_candidate_record(_candidate("A", 100.0, [step]), link_geometry, {"L1": 150.0})
    assert record.actual_duration_sec == 150.0
    assert record.quality == "high"


def test_assign_ranks_marks_best_candidate():
    a = type("C", (), {"actual_duration_sec": 200.0})()
    b = type("C", (), {"actual_duration_sec": 150.0})()
    assign_ranks([a, b])
    assert b.rank_actual == 1 and b.chosen_best is True
    assert a.rank_actual == 2 and a.chosen_best is False


def test_write_csv_writes_header_and_rows(tmp_path):
    rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
    path = write_csv(rows, tmp_path / "out.csv")
    text = path.read_text(encoding="utf-8-sig")
    assert "a,b" in text
    assert "1,x" in text and "2,y" in text


def test_write_csv_handles_empty_rows(tmp_path):
    path = write_csv([], tmp_path / "empty.csv")
    assert path.read_text(encoding="utf-8-sig") == ""