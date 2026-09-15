"""OSRM step → 링크 기하 map-match와 진행 방위 비교 검증."""
from types import SimpleNamespace

import pytest

from backend.src.services.route_prediction import (
    bearing_deg,
    bearing_difference,
    match_step_to_link,
    rank_candidates,
)


def step(name, coordinates, duration=600, distance=1000):
    return SimpleNamespace(name=name, duration_sec=duration, distance_m=distance, coordinates=coordinates)


def test_bearing_deg_and_difference():
    # 동쪽 진행은 90도, 서쪽은 270도이며 두 방위 차이는 180도입니다.
    assert bearing_deg((127.0, 37.5), (127.01, 37.5)) == pytest.approx(90, abs=0.1)
    assert bearing_deg((127.01, 37.5), (127.0, 37.5)) == pytest.approx(270, abs=0.1)
    assert bearing_difference(90, 100) == 10
    assert bearing_difference(350, 10) == 20
    assert bearing_difference(90, 270) == 180


def test_match_step_to_link_uses_distance_and_bearing():
    # step은 동쪽으로 진행하고, 링크도 동쪽 bearing이면 방향 일치로 판정합니다.
    links = [{"link_id": "L1", "segment": [(127.0, 37.5), (127.01, 37.5)], "bearing_deg": 90.0}]
    matched = match_step_to_link(step("강남대로", [(127.0, 37.5), (127.01, 37.5)]), links)
    assert matched["link_id"] == "L1"
    assert matched["direction_match"] is True
    assert matched["bearing_diff_deg"] == 0


def test_match_step_to_link_flags_opposite_direction():
    # 같은 링크라도 step이 서쪽으로 진행하면 방향 불일치로 표시합니다.
    links = [{"link_id": "L1", "segment": [(127.0, 37.5), (127.01, 37.5)], "bearing_deg": 90.0}]
    matched = match_step_to_link(step("강남대로", [(127.01, 37.5), (127.0, 37.5)]), links)
    assert matched["link_id"] == "L1"
    assert matched["direction_match"] is False
    assert matched["bearing_diff_deg"] == 180


def test_match_step_to_link_returns_none_without_coordinates():
    links = [{"link_id": "L1", "segment": [(127.0, 37.5), (127.01, 37.5)], "bearing_deg": 90.0}]
    assert match_step_to_link(step("강남대로", []), links) is None


def test_match_step_to_link_rejects_far_link():
    # 60m 밖 링크는 매칭하지 않고 link_id를 비웁니다.
    links = [{"link_id": "L1", "segment": [(127.1, 37.6), (127.11, 37.6)], "bearing_deg": 90.0}]
    matched = match_step_to_link(step("강남대로", [(127.0, 37.5), (127.01, 37.5)]), links)
    assert matched["link_id"] is None
    assert matched["direction_match"] is None


def test_rank_candidates_reports_link_and_direction_match_ratio():
    routes = [
        SimpleNamespace(
            id="A", duration_sec=600, distance_m=1000,
            steps=[step("강남대로", [(127.0, 37.5), (127.01, 37.5)])],
            coordinates=[(127.0, 37.5), (127.01, 37.5)],
        ),
    ]
    meta = [{"spot_name": "강남대로", "baseline": 100}]
    link_geometry = {
        "강남대로": [{"link_id": "L1", "segment": [(127.0, 37.5), (127.01, 37.5)], "bearing_deg": 90.0}],
    }
    result, _ = rank_candidates(routes, [100], meta, link_geometry=link_geometry)
    assert result[0]["link_match_ratio"] == 1
    assert result[0]["direction_match_ratio"] == 1
    assert result[0]["direction_matched_steps"] == 1
    assert result[0]["link_match_details"][0]["link_id"] == "L1"


def test_rank_candidates_without_link_geometry_marks_direction_unapplied():
    routes = [
        SimpleNamespace(
            id="A", duration_sec=600, distance_m=1000,
            steps=[step("강남대로", [(127.0, 37.5), (127.01, 37.5)])],
            coordinates=[(127.0, 37.5), (127.01, 37.5)],
        ),
    ]
    meta = [{"spot_name": "강남대로", "baseline": 100}]
    result, _ = rank_candidates(routes, [100], meta)
    assert result[0]["link_match_ratio"] == 0
    assert result[0]["direction_match_ratio"] is None
    assert result[0]["direction_matched_steps"] == 0