"""서울 주요 OD 쌍의 OSRM 후보 경로를 대량 시뮬레이션해 경로 학습 데이터셋을 구축합니다.

문제 정의서 §5.2·§8 단계 3을 구현합니다. production `/api/routes/predict`와 동일한
OSRM 요청(alternatives=3)을 사용하고, 링크 기하 map-match와 관측 속도 재구성을
재사용해 후보별 `actual_duration_sec`와 실제 순위 라벨을 만듭니다.

시간 누수 원칙: 피처는 출발 시각 이전 관측만(속도 lag, 활성 돌발, 기상), 라벨은 주행
시간대 관측만 사용합니다. 관측이 부족한 후보는 라벨을 비우고 품질을 `unusable`로 남깁니다.
"""

import csv
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from backend.src.services.route_duration_reconstruction import (
    OBSERVATION_WINDOW_MIN,
    QUALITY_UNUSABLE,
    load_link_observations,
    matched_link_ids,
    nearest_observation,
    quality_grade,
    reconstruct_candidate_duration,
    select_trip_observations,
)
from backend.src.services.route_prediction import (
    incident_category,
    load_road_link_geometry,
    match_step_to_links,
    road_key,
)

OSRM_BASE = "https://router.project-osrm.org"
# 출발 직전 속도 lag 피처로 허용하는 관측 지연(분)
FEATURE_LAG_WINDOW_MIN = 60
INCIDENT_CATEGORIES = ("accident", "construction", "control", "breakdown")


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


def match_candidate(candidate, link_geometry):
    """후보의 모든 step을 링크 기하에 map-match합니다. 반환: link_match_json과 같은 목록."""
    matches = []
    for index, step in enumerate(candidate["steps"]):
        step_match = match_step_to_links(step, link_geometry.get(road_key(step.name), [])) if step.name else None
        if step_match:
            matches.append({"index": index, "name": step.name, **step_match})
    return matches


@dataclass
class CandidateRecord:
    route_id: str
    route_distance_m: float
    osrm_duration_sec: float
    segment_count: int
    link_match_ratio: float
    direction_match_ratio: float | None
    opposite_direction_ratio: float
    actual_duration_sec: float | None
    actual_delay_sec: float | None
    quality: str
    observed_length_ratio: float
    features: dict = field(default_factory=dict)
    rank_actual: int | None = None
    chosen_best: bool | None = None


def build_candidate_record(candidate, matches, trip_observations, features=None):
    """후보 1개에 대해 재구성 라벨·매칭 품질을 계산합니다.

    matches: match_candidate 결과. trip_observations: {link_id: 관측} (주행 시간대).
    """
    steps = [{"name": s.name, "duration_sec": s.duration_sec, "distance_m": s.distance_m} for s in candidate["steps"]]
    result = reconstruct_candidate_duration(steps, matches, trip_observations)
    grade = quality_grade(result["total_m"], result["observed_m"])
    matched_m = sum(m["matched_m"] for m in matches)
    opposite_m = sum(m["opposite_m"] for m in matches)
    total_m = sum(m["total_m"] for m in matches) + sum(
        s.distance_m for i, s in enumerate(candidate["steps"]) if i not in {m["index"] for m in matches}
    )
    direction_flags = [m["direction_match"] for m in matches if m["direction_match"] is not None]
    usable = grade != QUALITY_UNUSABLE
    return CandidateRecord(
        route_id=candidate["route_id"],
        route_distance_m=candidate["distance_m"],
        osrm_duration_sec=candidate["duration_sec"],
        segment_count=len(candidate["steps"]),
        link_match_ratio=round(matched_m / total_m, 3) if total_m else 0.0,
        direction_match_ratio=round(sum(direction_flags) / len(direction_flags), 3) if direction_flags else None,
        opposite_direction_ratio=round(opposite_m / total_m, 3) if total_m else 0.0,
        actual_duration_sec=round(result["duration_sec"], 2) if usable else None,
        actual_delay_sec=round(result["duration_sec"] - candidate["duration_sec"], 2) if usable else None,
        quality=grade,
        observed_length_ratio=round(result["observed_m"] / result["total_m"], 3) if result["total_m"] else 0.0,
        features=dict(features or {}),
    )


def assign_ranks(candidates):
    """동일 요청 후보에 실제 통행시간 순위와 최적 경로 라벨을 부여합니다.

    라벨이 없는(unusable) 후보는 순위에서 제외하고, 비교 가능한 후보가 2개 미만이면 라벨을 비웁니다.
    """
    usable = [c for c in candidates if c.actual_duration_sec is not None]
    for candidate in candidates:
        candidate.rank_actual, candidate.chosen_best = None, None
    if len(usable) < 2:
        return candidates
    for rank, candidate in enumerate(sorted(usable, key=lambda c: c.actual_duration_sec), start=1):
        candidate.rank_actual = rank
        candidate.chosen_best = rank == 1
    return candidates


def speed_lag_features(matches, by_link, departure_at, window):
    """출발 직전 관측만으로 경로의 길이 가중 평균 속도와 커버리지를 계산합니다(누수 방지)."""
    weighted = covered = total = 0.0
    for match in matches:
        total += float(match.get("total_m") or 0.0)
        for part in match.get("links") or []:
            history = [o for o in by_link.get(part["link_id"], []) if o["measured_at"] <= departure_at]
            observation = nearest_observation(history, departure_at, window)
            if observation and observation.get("speed_kmh"):
                weighted += observation["speed_kmh"] * part["length_m"]
                covered += part["length_m"]
    return {
        "speed_lag_kmh": round(weighted / covered, 1) if covered else None,
        "speed_lag_coverage": round(covered / total, 3) if total else 0.0,
    }


def incident_features(matches, incidents_by_link):
    """매칭 링크 위에서 출발 시각에 활성인 돌발 건수를 유형별로 셉니다."""
    counts = {f"{category}_count": 0 for category in INCIDENT_CATEGORIES}
    seen = set()
    for link_id in matched_link_ids(matches):
        for incident in incidents_by_link.get(link_id, []):
            if incident["incident_id"] in seen:
                continue
            seen.add(incident["incident_id"])
            key = f"{incident_category(incident)}_count"
            if key in counts:
                counts[key] += 1
    counts["active_incident_count"] = len(seen)
    return counts


class RouteTrainingDatasetBuilder:
    def __init__(self, db: Session, fetch_candidates=fetch_osrm_candidates, sleep_sec=0.2,
                 window_minutes=OBSERVATION_WINDOW_MIN):
        self.db = db
        self.fetch_candidates = fetch_candidates
        self.sleep_sec = sleep_sec
        self.window = timedelta(minutes=window_minutes)
        self.lag_window = timedelta(minutes=FEATURE_LAG_WINDOW_MIN)

    def build(self, od_pairs, departures, limit=None):
        """OD 쌍과 출발 시각마다 후보를 생성하고 실제 순위를 부여합니다.

        OSRM 후보는 OD 쌍당 한 번만 조회하고 출발 시각마다 관측만 바꿔 붙입니다.
        """
        link_geometry = load_road_link_geometry(self.db)
        rows = []
        for origin, destination in od_pairs:
            candidates = self.fetch_candidates(origin, destination)
            if not candidates:
                continue
            matched = [(candidate, match_candidate(candidate, link_geometry)) for candidate in candidates]
            link_ids = set().union(*(matched_link_ids(m) for _, m in matched))
            for departure_at in departures:
                longest = max(c["duration_sec"] for c in candidates)
                by_link = load_link_observations(
                    self.db, link_ids, departure_at - self.lag_window,
                    departure_at + timedelta(seconds=longest) + self.window,
                )
                incidents = self._load_active_incidents(link_ids, departure_at)
                weather = self._load_weather(departure_at)
                records = []
                for candidate, matches in matched:
                    trip = select_trip_observations(by_link, matched_link_ids(matches), departure_at,
                                                    candidate["duration_sec"], self.window)
                    features = {
                        **speed_lag_features(matches, by_link, departure_at, self.lag_window),
                        **incident_features(matches, incidents),
                        **weather,
                    }
                    records.append(build_candidate_record(candidate, matches, trip, features))
                assign_ranks(records)
                request_id = f"{origin['name']}->{destination['name']}@{departure_at:%Y%m%d%H%M}"
                for record in records:
                    rows.append(self._row(request_id, origin, destination, departure_at, record))
                if limit is not None and len(rows) >= limit:
                    return rows
            if self.sleep_sec:
                time.sleep(self.sleep_sec)
        return rows

    @staticmethod
    def _row(request_id, origin, destination, departure_at, record):
        weekday = departure_at.weekday()
        return {
            "route_request_id": request_id,
            "route_id": record.route_id,
            "departure_at": departure_at.isoformat(),
            "departure_hour": departure_at.hour,
            "weekday": weekday,
            "is_weekend": int(weekday >= 5),
            "origin_name": origin["name"], "origin_lat": origin["lat"], "origin_lng": origin["lng"],
            "destination_name": destination["name"],
            "destination_lat": destination["lat"], "destination_lng": destination["lng"],
            "route_distance_m": record.route_distance_m,
            "osrm_duration_sec": record.osrm_duration_sec,
            "segment_count": record.segment_count,
            "link_match_ratio": record.link_match_ratio,
            "direction_match_ratio": record.direction_match_ratio,
            "opposite_direction_ratio": record.opposite_direction_ratio,
            **record.features,
            "actual_duration_sec": record.actual_duration_sec,
            "actual_delay_sec": record.actual_delay_sec,
            "actual_duration_quality": record.quality,
            "observed_length_ratio": record.observed_length_ratio,
            "route_rank_actual": record.rank_actual,
            "chosen_best": record.chosen_best,
        }

    def _load_active_incidents(self, link_ids, departure_at):
        if not link_ids:
            return {}
        rows = self.db.execute(text("""
            SELECT incident_id, link_id, incident_type, incident_detail_type, occurred_at, expected_clear_at
            FROM incidents
            WHERE link_id IN :link_ids
              AND occurred_at <= :departure_at
              AND (expected_clear_at IS NULL OR expected_clear_at >= :departure_at)
        """).bindparams(bindparam("link_ids", expanding=True)),
            {"link_ids": list(link_ids), "departure_at": departure_at}).mappings()
        by_link = {}
        for row in rows:
            by_link.setdefault(row["link_id"], []).append(dict(row))
        return by_link

    def _load_weather(self, departure_at):
        """출발 시각 이전 마지막 기상 관측(108 관측소)만 사용합니다."""
        row = self.db.execute(text("""
            SELECT temperature_c, rainfall_mm, humidity_pct, observed_at
            FROM weather_measurements
            WHERE weather_station_id = '108' AND observed_at <= :departure_at
            ORDER BY observed_at DESC LIMIT 1
        """), {"departure_at": departure_at}).mappings().first()
        if not row:
            return {"weather_temperature_c": None, "weather_rainfall_mm": None,
                    "weather_humidity_pct": None, "weather_age_hours": None}
        return {
            "weather_temperature_c": float(row["temperature_c"]) if row["temperature_c"] is not None else None,
            "weather_rainfall_mm": float(row["rainfall_mm"] or 0.0),
            "weather_humidity_pct": float(row["humidity_pct"]) if row["humidity_pct"] is not None else None,
            "weather_age_hours": round((departure_at - row["observed_at"]).total_seconds() / 3600, 2),
        }


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
