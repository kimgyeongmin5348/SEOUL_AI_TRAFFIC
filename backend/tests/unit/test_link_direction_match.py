"""OSRM step → 링크 기하 map-match와 진행 방위 비교 검증."""
from types import SimpleNamespace

import pytest

from backend.src.services.route_prediction import (
    bearing_deg,
    bearing_difference,
    match_step_to_links,
    rank_candidates,
    sample_step,
)

# 경도 0.001° ≈ 88m (위도 37.5°)
LAT = 37.5


def step(name, coordinates, duration=600, distance=1000):
    return SimpleNamespace(name=name, duration_sec=duration, distance_m=distance, coordinates=coordinates)


def link(link_id, x0, x1, bearing=90.0, lat=LAT):
    return {"link_id": link_id, "polyline": [(x0, lat), (x1, lat)], "bearing_deg": bearing, "length_m": abs(x1 - x0) * 88000}


def test_bearing_deg_and_difference():
    # 동쪽 진행은 90도, 서쪽은 270도이며 두 방위 차이는 180도입니다.
    assert bearing_deg((127.0, 37.5), (127.01, 37.5)) == pytest.approx(90, abs=0.1)
    assert bearing_deg((127.01, 37.5), (127.0, 37.5)) == pytest.approx(270, abs=0.1)
    assert bearing_difference(90, 100) == 10
    assert bearing_difference(350, 10) == 20
    assert bearing_difference(90, 270) == 180


def test_sample_step_splits_long_segments_and_keeps_total_length():
    samples = list(sample_step([(127.0, LAT), (127.003, LAT)], spacing_m=100))
    assert len(samples) == 3  # 264m → 100m 간격 3조각
    assert sum(weight for _, _, weight in samples) == pytest.approx(264, abs=2)
    assert all(bearing == pytest.approx(90, abs=0.1) for _, bearing, _ in samples)


def test_match_step_distributes_length_over_multiple_links():
    # 264m step이 링크 두 개(0~0.001, 0.001~0.003)에 걸치면 길이가 88 / 176으로 나뉩니다.
    links = [link("L1", 127.0, 127.001), link("L2", 127.001, 127.003)]
    matched = match_step_to_links(step("강남대로", [(127.0, LAT), (127.003, LAT)]), links)
    parts = {p["link_id"]: p["length_m"] for p in matched["links"]}
    assert parts["L1"] == pytest.approx(88, abs=2) and parts["L2"] == pytest.approx(176, abs=3)
    assert matched["link_id"] == "L2"  # 길이가 가장 긴 링크가 대표
    assert matched["match_ratio"] == 1.0 and matched["direction_match"] is True
    assert matched["opposite_m"] == 0 and matched["unmatched_m"] == 0


def test_match_step_prefers_direction_aligned_link_over_nearer_opposite_link():
    # 양방향 도로: 서행 링크가 10m로 더 가깝고 동행 링크는 30m 떨어져 있어도 진행 방향(동) 링크를 고릅니다.
    east = link("E", 127.0, 127.002, bearing=90.0, lat=LAT + 0.00027)   # 약 30m 북쪽
    west = link("W", 127.002, 127.0, bearing=270.0, lat=LAT + 0.00009)  # 약 10m 북쪽
    matched = match_step_to_links(step("강남대로", [(127.0, LAT), (127.002, LAT)]), [west, east])
    assert matched["link_id"] == "E" and matched["direction_match"] is True
    assert matched["opposite_m"] == 0


def test_match_step_counts_opposite_direction_when_only_reverse_link_is_near():
    # 같은 위치에 서행 링크만 있으면 링크를 배분하지 않고 반대 방향 길이로 셉니다.
    links = [link("W", 127.002, 127.0, bearing=270.0)]
    matched = match_step_to_links(step("강남대로", [(127.0, LAT), (127.002, LAT)]), links)
    assert matched["links"] == [] and matched["link_id"] is None
    assert matched["direction_match"] is False
    assert matched["opposite_m"] == pytest.approx(176, abs=3) and matched["match_ratio"] == 0


def test_match_step_uses_polyline_not_chord_for_curved_links():
    # ㄱ자 링크: 시·종점 직선(현)과 실제 도로는 멀지만 폴리라인으로는 매칭됩니다.
    curved = {"link_id": "C", "bearing_deg": 135.0, "length_m": 176,
              "polyline": [(127.0, LAT + 0.001), (127.001, LAT + 0.001), (127.001, LAT)]}
    coordinates = [(127.0, LAT + 0.001), (127.001, LAT + 0.001), (127.001, LAT)]
    matched = match_step_to_links(step("순환로", coordinates), [curved])
    assert matched["link_id"] == "C" and matched["match_ratio"] == 1.0


def test_match_step_returns_none_without_coordinates_and_marks_far_links_unmatched():
    links = [link("L1", 127.0, 127.01)]
    assert match_step_to_links(step("강남대로", []), links) is None
    far = match_step_to_links(step("강남대로", [(127.0, LAT), (127.002, LAT)]), [link("F", 127.1, 127.11, lat=37.6)])
    assert far["link_id"] is None and far["direction_match"] is None
    assert far["unmatched_m"] == far["total_m"] and far["match_ratio"] == 0


def test_rank_candidates_reports_length_based_link_and_direction_match_ratio():
    routes = [
        SimpleNamespace(
            id="A", duration_sec=600, distance_m=1000,
            steps=[step("강남대로", [(127.0, LAT), (127.002, LAT)], distance=176),
                   step("테헤란로", [(127.002, LAT), (127.004, LAT)], distance=176)],
            coordinates=[(127.0, LAT), (127.004, LAT)],
        ),
    ]
    meta = [{"spot_name": "강남대로", "baseline": 100}]
    link_geometry = {"강남대로": [link("L1", 127.0, 127.002)]}  # 테헤란로는 기하 없음
    result, _ = rank_candidates(routes, [100], meta, link_geometry=link_geometry)
    assert result[0]["link_match_ratio"] == pytest.approx(0.5, abs=0.02)
    assert result[0]["direction_match_ratio"] == 1 and result[0]["direction_matched_steps"] == 1
    details = result[0]["link_match_details"]
    assert details[0]["index"] == 0 and details[0]["link_id"] == "L1"
    assert details[0]["links"][0]["length_m"] == pytest.approx(176, abs=3)
    assert result[0]["link_matched_road_names"] == ["강남대로"]


def test_rank_candidates_without_link_geometry_marks_direction_unapplied():
    routes = [
        SimpleNamespace(
            id="A", duration_sec=600, distance_m=1000,
            steps=[step("강남대로", [(127.0, LAT), (127.01, LAT)])],
            coordinates=[(127.0, LAT), (127.01, LAT)],
        ),
    ]
    meta = [{"spot_name": "강남대로", "baseline": 100}]
    result, _ = rank_candidates(routes, [100], meta)
    assert result[0]["link_match_ratio"] == 0
    assert result[0]["direction_match_ratio"] is None
    assert result[0]["direction_matched_steps"] == 0
