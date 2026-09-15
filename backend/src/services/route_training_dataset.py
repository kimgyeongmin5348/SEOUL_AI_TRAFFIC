"""서울 주요 OD 쌍의 OSRM 후보 경로를 대량 시뮬레이션해 경로 학습 데이터셋을 구축합니다.

문제 정의서 §5.2·§8 단계 3을 구현합니다. production `/api/routes/predict`와 동일한
OSRM 요청(alternatives=3)을 사용하고, 링크 기하 map-match와 관측 통행시간 재구성을
재사용해 후보별 `actual_duration_sec`와 실제 순위 라벨을 만듭니다.
"""

import csv
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend.src.services.route_duration_reconstruction import (
    quality_grade,
    reconstruct_candidate_duration,
)
from backend.src.services.route_prediction import (
    load_road_link_geometry,
    match_step_to_link,
    road_key,
)

OSRM_BASE = "https://router.project-osrm.org"
# 관측 통행시간을 찾을 때 출발 시각 기준 허용 시간 창(분)
OBSERVATION_WINDOW_MIN = 60


@dataclass
class OsrmStep:
    name: str
    duration_sec: float
    distance_m: float
    coordinates: list


def parse_osrm_routes(payload):
    """OSRM 응답을 후보 경로 목록으로 변환합니다(최대 3개)."""
    candidates = []
    for index, route in enumerate((payload.get("routes") or [])[:3]):
        steps = []
        for leg in route.get("legs") or []:
            for step in leg.get("steps") or []:
                steps.append(OsrmStep(
                    name=(step.get("name") or "").strip(),
                    duration_sec=float(step.get("duration") or 0.0),
                    distance_m=float(step.get("distance") or 0.0),
                    coordinates=(step.get("geometry") or {}).get("coordinates") or [],
                ))
        candidates.append({
            "route_id": chr(65 + index),
            "distance_m": float(route.get("distance") or 0.0),
            "duration_sec": float(route.get("duration") or 0.0),
            "coordinates": (route.get("geometry") or {}).get("coordinates") or [],
            "steps": steps,
        })
    return candidates


def fetch_osrm_candidates(origin, destination, timeout=10.0):
    """production과 동일한 OSRM 요청으로 후보 경로를 가져옵니다."""
    coords = f"{origin['lng']},{origin['lat']};{destination['lng']},{destination['lat']}"
    query = urllib.parse.urlencode({
        "overview": "full", "alternatives": 3, "geometries": "geojson", "steps": "true",
    })
    url = f"{OSRM_BASE}/route/v1/driving/{coords}?{query}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_osrm_routes(payload)


@dataclass
class CandidateRecord:
    route_id: str
    route_distance_m: float
    osrm_duration_sec: float
    segment_count: int
    link_match_ratio: float
    direction_match_ratio: float | None
    actual_duration_sec: float
    actual_delay_sec: float
    quality: str
    rank_actual: int = 0
    chosen_best: bool = False


def build_candidate_record(candidate, link_geometry, travel_times):
    """후보 1개에 대해 map-match·재구성·품질 등급을 계산합니다."""
    matches = []
    direction_flags = []
    link_ids = set()
    for index, step in enumerate(candidate["steps"]):
        step_match = match_step_to_link(step, link_geometry.get(road_key(step.name), [])) if step.name else None
        if not step_match:
            continue
        matches.append({"index": index, **step_match})
        if step_match.get("link_id"):
            link_ids.add(step_match["link_id"])
        if step_match.get("direction_match") is not None:
            direction_flags.append(bool(step_match["direction_match"]))
    used_times = {link_id: value for link_id, value in travel_times.items() if link_id in link_ids}
    actual, observed_steps, matched_steps = reconstruct_candidate_duration(
        [{"name": s.name, "duration_sec": s.duration_sec, "distance_m": s.distance_m} for s in candidate["steps"]],
        matches,
        used_times,
    )
    step_count = len(candidate["steps"])
    return CandidateRecord(
        route_id=candidate["route_id"],
        route_distance_m=candidate["distance_m"],
        osrm_duration_sec=candidate["duration_sec"],
        segment_count=step_count,
        link_match_ratio=round(matched_steps / step_count, 3) if step_count else 0.0,
        direction_match_ratio=round(sum(direction_flags) / len(direction_flags), 3) if direction_flags else None,
        actual_duration_sec=round(actual, 2),
        actual_delay_sec=round(actual - candidate["duration_sec"], 2),
        quality=quality_grade(step_count, matched_steps, observed_steps),
    )


def assign_ranks(candidates):
    """동일 요청 후보에 실제 통행시간 순위와 최적 경로 라벨을 부여합니다."""
    ordered = sorted(candidates, key=lambda c: c.actual_duration_sec)
    for rank, candidate in enumerate(ordered, start=1):
        candidate.rank_actual = rank
        candidate.chosen_best = rank == 1
    return candidates


class RouteTrainingDatasetBuilder:
    def __init__(self, db: Session, fetch_candidates=fetch_osrm_candidates, sleep_sec=0.2):
        self.db = db
        self.fetch_candidates = fetch_candidates
        self.sleep_sec = sleep_sec

    def build(self, od_pairs, departures, limit=None):
        """OD 쌍과 출발 시각마다 후보를 생성하고 실제 순위를 부여합니다."""
        link_geometry = load_road_link_geometry(self.db)
        rows = []
        for origin, destination in od_pairs:
            for departure_at in departures:
                candidates = self.fetch_candidates(origin, destination)
                if not candidates:
                    continue
                link_ids = self._collect_link_ids(candidates, link_geometry)
                travel_times = self._load_travel_times(link_ids, departure_at)
                records = [build_candidate_record(c, link_geometry, travel_times) for c in candidates]
                assign_ranks(records)
                request_id = f"{origin['name']}->{destination['name']}@{departure_at:%Y%m%d%H}"
                for record in records:
                    rows.append({
                        "route_request_id": request_id,
                        "route_id": record.route_id,
                        "departure_at": departure_at.isoformat(),
                        "origin_name": origin["name"], "origin_lat": origin["lat"], "origin_lng": origin["lng"],
                        "destination_name": destination["name"],
                        "destination_lat": destination["lat"], "destination_lng": destination["lng"],
                        "route_distance_m": record.route_distance_m,
                        "osrm_duration_sec": record.osrm_duration_sec,
                        "segment_count": record.segment_count,
                        "link_match_ratio": record.link_match_ratio,
                        "direction_match_ratio": record.direction_match_ratio,
                        "actual_duration_sec": record.actual_duration_sec,
                        "actual_delay_sec": record.actual_delay_sec,
                        "actual_duration_quality": record.quality,
                        "route_rank_actual": record.rank_actual,
                        "chosen_best": record.chosen_best,
                    })
                if limit is not None and len(rows) >= limit:
                    return rows
                if self.sleep_sec:
                    time.sleep(self.sleep_sec)
        return rows

    def _collect_link_ids(self, candidates, link_geometry):
        link_ids = set()
        for candidate in candidates:
            for step in candidate["steps"]:
                match = match_step_to_link(step, link_geometry.get(road_key(step.name), [])) if step.name else None
                if match and match.get("link_id"):
                    link_ids.add(match["link_id"])
        return link_ids

    def _load_travel_times(self, link_ids, departure_at):
        if not link_ids:
            return {}
        start = departure_at - timedelta(minutes=OBSERVATION_WINDOW_MIN)
        end = departure_at + timedelta(minutes=OBSERVATION_WINDOW_MIN)
        result = self.db.execute(text("""
            SELECT link_id, measured_at, travel_time_sec
            FROM traffic_speed_measurements
            WHERE link_id IN :link_ids AND measured_at >= :start AND measured_at <= :end
        """).bindparams(bindparam("link_ids", expanding=True)),
            {"link_ids": list(link_ids), "start": start, "end": end}).mappings()
        by_link = {}
        for row in result:
            existing = by_link.get(row["link_id"])
            if existing is None or abs((row["measured_at"] - departure_at).total_seconds()) < \
                    abs((existing[0] - departure_at).total_seconds()):
                by_link[row["link_id"]] = (row["measured_at"], float(row["travel_time_sec"]))
        return {link_id: value[1] for link_id, value in by_link.items()}


def write_csv(rows, path: Path):
    """경로 학습 데이터셋을 CSV로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return path
    columns = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path