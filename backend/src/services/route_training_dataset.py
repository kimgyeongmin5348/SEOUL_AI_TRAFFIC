"""서울 주요 OD 쌍의 OSRM 후보 경로를 대량 시뮬레이션해 경로 학습 데이터셋을 구축합니다.

문제 정의서 §5.2·§6·§8 단계 3을 구현합니다. production `/api/routes/predict`와 동일한
OSRM 요청(alternatives=3)을 사용하고, 링크 기하 map-match와 관측 속도 재구성을
재사용해 후보별 `actual_duration_sec`와 실제 순위 라벨을 만듭니다.

시간 누수 원칙: 피처는 출발 시각 이전에 *수집된* 값만(속도 lag, 교통량 lag는 collected_at 기준,
활성 돌발, 전일 기상), 라벨은 주행 시간대 관측만 사용합니다. 관측이 부족한 후보는 라벨을 비우고
품질을 `unusable`로 남깁니다. 각 피처가 참조한 최신 관측 시각을 함께 저장해 검사 스크립트가
누수를 자동 검증합니다.
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
# 교통량(VolInfo)은 시간 단위이고 게시가 2시간 정도 늦으므로 출발 전 6시간까지 거슬러 찾습니다.
VOLUME_LAG_WINDOW_HOURS = 6
# DB의 collected_at은 UTC, measured_at·departure_at은 KST naive입니다.
KST_OFFSET = timedelta(hours=9)
INCIDENT_CATEGORIES = ("accident", "construction", "control", "breakdown")
# 정의서 §3.7: 통제처럼 통행 불가인 유형은 큰 비용. 심각도는 유형별 정수 등급입니다.
INCIDENT_SEVERITY = {"control": 3, "accident": 2, "construction": 1, "breakdown": 1, "other": 1}
# 통제 중에서도 '전면·차단'으로 표기된 돌발은 주행 불가(blocked)로 봅니다.
BLOCKED_KEYWORDS = ("전면", "차단", "통행금지", "폐쇄")


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


def matched_length_by_link(matches):
    """{link_id: 이 경로에서 그 링크에 배분된 길이 m}"""
    lengths = {}
    for match in matches:
        for part in match.get("links") or []:
            lengths[part["link_id"]] = lengths.get(part["link_id"], 0.0) + float(part.get("length_m") or 0.0)
    return lengths


def route_total_m(candidate, matches):
    matched_indexes = {m["index"] for m in matches}
    # 온라인 요청의 step distance_m은 선택 필드라 None일 수 있습니다.
    return sum(m["total_m"] for m in matches) + sum(
        float(s.distance_m or 0.0) for i, s in enumerate(candidate["steps"]) if i not in matched_indexes
    )


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
    label_observed_at_min: object = None
    label_observed_at_max: object = None
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
    total_m = route_total_m(candidate, matches)
    direction_flags = [m["direction_match"] for m in matches if m["direction_match"] is not None]
    usable = grade != QUALITY_UNUSABLE
    observed_times = [o["measured_at"] for o in trip_observations.values() if o.get("measured_at")]
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
        label_observed_at_min=min(observed_times) if observed_times else None,
        label_observed_at_max=max(observed_times) if observed_times else None,
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
    """출발 직전 관측만으로 경로의 길이 가중 평균·최저 속도, 통행시간 합, 커버리지를 계산합니다(누수 방지)."""
    weighted = covered = total = lag_sec = 0.0
    slowest, latest = None, None
    for match in matches:
        total += float(match.get("total_m") or 0.0)
        for part in match.get("links") or []:
            history = [o for o in by_link.get(part["link_id"], []) if o["measured_at"] <= departure_at]
            observation = nearest_observation(history, departure_at, window)
            if observation and observation.get("speed_kmh"):
                weighted += observation["speed_kmh"] * part["length_m"]
                covered += part["length_m"]
                lag_sec += part["length_m"] / (observation["speed_kmh"] / 3.6)
                slowest = observation["speed_kmh"] if slowest is None else min(slowest, observation["speed_kmh"])
                latest = observation["measured_at"] if latest is None else max(latest, observation["measured_at"])
    return {
        "speed_lag_kmh": round(weighted / covered, 1) if covered else None,
        "speed_lag_min_kmh": round(slowest, 1) if slowest is not None else None,
        "speed_lag_travel_time_sec": round(lag_sec, 1) if covered else None,
        "speed_lag_coverage": round(covered / total, 3) if total else 0.0,
        "speed_lag_age_min": round((departure_at - latest).total_seconds() / 60, 1) if latest else None,
        "speed_lag_observed_at": latest,
        "speed_data_available": int(covered > 0),
    }


def volume_lag_features(matches, volumes_by_link, departure_at):
    """매칭 링크에 연결된 측정지점의 출발 전 최신 시간 교통량(대/시)을 집계합니다.

    측정지점→링크 매핑(traffic_spot_road_maps)은 진행 방향을 구분하지 않으므로 지점 합계(양방향)를
    씁니다. 측정지점은 139개뿐이라 커버리지가 낮은 편이며 그 비율을 함께 남깁니다.
    """
    lengths = matched_length_by_link(matches)
    total = sum(m.get("total_m") or 0.0 for m in matches)
    weighted = covered = 0.0
    values, latest = [], None
    for link_id, length in lengths.items():
        row = volumes_by_link.get(link_id)
        if not row:
            continue
        weighted += row["volume"] * length
        covered += length
        values.append(row["volume"])
        latest = row["measured_at"] if latest is None else max(latest, row["measured_at"])
    return {
        "volume_lag_vph_mean": round(weighted / covered, 1) if covered else None,
        "volume_lag_vph_max": round(max(values), 1) if values else None,
        "volume_lag_coverage": round(covered / total, 3) if total else 0.0,
        "volume_lag_age_hours": round((departure_at - latest).total_seconds() / 3600, 2) if latest else None,
        "volume_lag_observed_at": latest,
    }


def incident_features(matches, incidents_by_link, departure_at, osrm_duration_sec, total_m, data_age_sec=None):
    """매칭 링크 위에서 출발 시각에 활성인 돌발의 건수·유형·심각도·길이·해제시각 겹침을 계산합니다.

    - control_length_m: 통제 유형 돌발이 있는 링크에 배분된 경로 길이
    - blocked_length_m: 그중 '전면·차단' 표기가 있는 돌발(주행 불가)의 길이
    - incident_clear_overlap_sec: 예상 해제시각까지 남은 시간과 주행 시간이 겹치는 초(최댓값)
    - incident_impact_score: Σ 심각도 × (영향 길이 / 경로 길이) × 겹침 비율
    - incident_match_ratio: 돌발을 판정할 수 있는(링크가 매칭된) 경로 길이 비율
    """
    lengths = matched_length_by_link(matches)
    counts = {f"{category}_count": 0 for category in INCIDENT_CATEGORIES}
    seen, control_m, blocked_m, severity_max, impact, overlap_max = set(), 0.0, 0.0, 0, 0.0, 0.0
    duration = max(1.0, float(osrm_duration_sec or 0.0))
    for link_id, length in lengths.items():
        for incident in incidents_by_link.get(link_id, []):
            if incident["incident_id"] in seen:
                continue
            seen.add(incident["incident_id"])
            category = incident_category(incident)
            key = f"{category}_count"
            if key in counts:
                counts[key] += 1
            severity = INCIDENT_SEVERITY.get(category, 1)
            severity_max = max(severity_max, severity)
            clear_at = incident.get("expected_clear_at")
            remaining = (clear_at - departure_at).total_seconds() if clear_at else duration
            overlap = max(0.0, min(remaining, duration))
            overlap_max = max(overlap_max, overlap)
            impact += severity * (length / total_m if total_m else 0.0) * (overlap / duration)
            if category == "control":
                control_m += length
                text_value = " ".join(str(incident.get(k) or "") for k in ("incident_detail_type", "description"))
                if any(word in text_value for word in BLOCKED_KEYWORDS):
                    blocked_m += length
    return {
        **counts,
        "active_incident_count": len(seen),
        "control_length_m": round(control_m, 1),
        "blocked_length_m": round(blocked_m, 1),
        "incident_severity_max": severity_max,
        "incident_impact_score": round(impact, 4),
        "incident_clear_overlap_sec": round(overlap_max, 1),
        "incident_match_ratio": round(sum(lengths.values()) / total_m, 3) if total_m else 0.0,
        "incident_data_age_sec": data_age_sec,
    }


def load_spot_links(db):
    """{link_id: spot_id} — 교통량 측정지점이 연결된 링크만."""
    rows = db.execute(text("SELECT link_id, spot_id FROM traffic_spot_road_maps")).fetchall()
    return {row[0]: row[1] for row in rows}


def load_active_incidents_by_link(db, link_ids, departure_at):
    """출발 시각에 활성이고, 출발 전에 수집된(collected_at UTC) 돌발만. {link_id: [돌발...]}"""
    if not link_ids:
        return {}
    rows = db.execute(text("""
        SELECT incident_id, link_id, incident_type, incident_detail_type, description,
               occurred_at, expected_clear_at
        FROM incidents
        WHERE link_id IN :link_ids
          AND occurred_at <= :departure_at
          AND collected_at <= :departure_utc
          AND (expected_clear_at IS NULL OR expected_clear_at >= :departure_at)
    """).bindparams(bindparam("link_ids", expanding=True)),
        {"link_ids": list(link_ids), "departure_at": departure_at,
         "departure_utc": departure_at - KST_OFFSET}).mappings()
    by_link = {}
    for row in rows:
        by_link.setdefault(row["link_id"], []).append(dict(row))
    return by_link


def incident_data_age_sec(db, departure_at):
    """출발 시각 기준 돌발 데이터 지연(마지막 수집 이후 초)."""
    latest = db.execute(text("SELECT MAX(collected_at) FROM incidents WHERE collected_at <= :departure_utc"),
                        {"departure_utc": departure_at - KST_OFFSET}).scalar()
    return round((departure_at - KST_OFFSET - latest).total_seconds()) if latest else None


def load_volume_lag(db, link_ids, spot_links, departure_at):
    """매칭 링크의 측정지점별 최신 시간 교통량(양방향·전 차로 합). 출발 전 수집분만. {link_id: {...}}"""
    spots = {spot_links[link_id] for link_id in link_ids if link_id in spot_links}
    if not spots:
        return {}
    rows = db.execute(text("""
        SELECT spot_id, measured_at, SUM(traffic_volume) AS volume
        FROM traffic_volume_measurements
        WHERE spot_id IN :spots
          AND collected_at <= :departure_utc
          AND measured_at >= :start AND measured_at <= :departure_at
        GROUP BY spot_id, measured_at
    """).bindparams(bindparam("spots", expanding=True)),
        {"spots": list(spots), "departure_utc": departure_at - KST_OFFSET,
         "start": departure_at - timedelta(hours=VOLUME_LAG_WINDOW_HOURS), "departure_at": departure_at}).mappings()
    latest = {}
    for row in rows:
        if row["spot_id"] not in latest or row["measured_at"] > latest[row["spot_id"]]["measured_at"]:
            latest[row["spot_id"]] = {"measured_at": row["measured_at"], "volume": float(row["volume"])}
    return {link_id: latest[spot] for link_id, spot in spot_links.items() if spot in latest}


def load_weather_before(db, departure_at):
    """출발 시각 이전 마지막 기상 관측(108 관측소)만 사용합니다."""
    row = db.execute(text("""
        SELECT temperature_c, rainfall_mm, humidity_pct, observed_at
        FROM weather_measurements
        WHERE weather_station_id = '108' AND observed_at <= :departure_at
        ORDER BY observed_at DESC LIMIT 1
    """), {"departure_at": departure_at}).mappings().first()
    return weather_features(row, departure_at)


def weather_features(row, departure_at):
    """기상 관측 행 → 피처. 학습(데이터셋)과 온라인 추론이 같은 변환을 씁니다."""
    if not row:
        return {"weather_temperature_c": None, "weather_rainfall_mm": None,
                "weather_humidity_pct": None, "weather_age_hours": None, "weather_observed_at": None}
    return {
        "weather_temperature_c": float(row["temperature_c"]) if row["temperature_c"] is not None else None,
        "weather_rainfall_mm": float(row["rainfall_mm"] or 0.0),
        "weather_humidity_pct": float(row["humidity_pct"]) if row["humidity_pct"] is not None else None,
        "weather_age_hours": round((departure_at - row["observed_at"]).total_seconds() / 3600, 2),
        "weather_observed_at": row["observed_at"],
    }


def candidate_features(matches, by_link, volumes, incidents, weather, departure_at, osrm_duration_sec, total_m,
                       lag_window, incident_age=None):
    """후보 1개의 모델 입력 피처. 데이터셋 생성과 온라인 추론이 이 함수 하나를 공유합니다."""
    return {
        **speed_lag_features(matches, by_link, departure_at, lag_window),
        **volume_lag_features(matches, volumes, departure_at),
        **incident_features(matches, incidents, departure_at, osrm_duration_sec, total_m, incident_age),
        **weather,
    }


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
        spot_links = load_spot_links(self.db)
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
                incidents = load_active_incidents_by_link(self.db, link_ids, departure_at)
                incident_age = incident_data_age_sec(self.db, departure_at)
                volumes = load_volume_lag(self.db, link_ids, spot_links, departure_at)
                weather = load_weather_before(self.db, departure_at)
                records = []
                for candidate, matches in matched:
                    trip = select_trip_observations(by_link, matched_link_ids(matches), departure_at,
                                                    candidate["duration_sec"], self.window)
                    features = candidate_features(
                        matches, by_link, volumes, incidents, weather, departure_at,
                        candidate["duration_sec"], route_total_m(candidate, matches), self.lag_window, incident_age,
                    )
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
        stamp = lambda value: value.isoformat() if value is not None else None  # noqa: E731
        features = {k: (stamp(v) if k.endswith("_observed_at") else v) for k, v in record.features.items()}
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
            **features,
            "actual_duration_sec": record.actual_duration_sec,
            "actual_delay_sec": record.actual_delay_sec,
            "actual_duration_quality": record.quality,
            "observed_length_ratio": record.observed_length_ratio,
            "label_observed_at_min": stamp(record.label_observed_at_min),
            "label_observed_at_max": stamp(record.label_observed_at_max),
            "route_rank_actual": record.rank_actual,
            "chosen_best": record.chosen_best,
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
