"""경로 후보의 actual_duration_sec를 링크 관측 속도로 재구성합니다.

실제 주행 이력이 없으므로, OSRM step을 링크 기하에 map-match한 결과(link_match_json)와
주행 시간대의 traffic_speed_measurements 관측을 결합해 경로 통행시간을 재구성합니다.

- step에 배분된 링크 길이마다 그 링크의 관측 속도로 통과 시간을 계산합니다.
  (링크 통행시간을 그대로 대체하면 step 길이와 링크 길이가 달라 값이 왜곡됩니다.)
- 반대 방향 링크에만 붙은 구간과 미매칭 구간은 OSRM 시간을 길이 비례로 유지합니다.
- 관측으로 설명된 길이 비율이 낮으면 라벨을 만들지 않고 `unusable`로 남깁니다.
"""

import json
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

# 주행 시각과 관측 시각의 허용 차이(분). 이보다 멀면 해당 링크 관측을 쓰지 않습니다.
OBSERVATION_WINDOW_MIN = 60
# 관측으로 설명된 길이 비율이 이 값 미만이면 라벨을 만들지 않습니다.
LABEL_MIN_OBSERVED_RATIO = 0.3
QUALITY_UNUSABLE = "unusable"


def _parse_json(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    return json.loads(value)


def portion_seconds(length_m, observation):
    """링크 관측으로 length_m 구간의 통과 시간(초)을 계산합니다.

    observation: {"speed_kmh", "travel_time_sec", "length_m"}. 속도가 있으면 속도로,
    없으면 링크 통행시간을 링크 길이로 나눈 비율로 계산합니다. 둘 다 없으면 None.
    """
    speed = observation.get("speed_kmh")
    if speed and float(speed) > 0:
        return float(length_m) / (float(speed) / 3.6)
    travel_time, link_length = observation.get("travel_time_sec"), observation.get("length_m")
    if travel_time is not None and link_length and float(link_length) > 0:
        return float(length_m) * float(travel_time) / float(link_length)
    return None


def reconstruct_candidate_duration(steps, link_matches, observations):
    """step별 OSRM 시간과 링크 관측 속도를 결합해 경로 통행시간을 재구성합니다.

    steps: [{"name", "duration_sec", "distance_m"}, ...]
    link_matches: [{"index", "links": [{"link_id", "length_m"}, ...], "total_m", ...}, ...]
    observations: {link_id: {"speed_kmh", "travel_time_sec", "length_m"}}
    반환: {"duration_sec", "observed_m", "total_m", "observed_steps"}
    """
    by_index = {m["index"]: m for m in link_matches if m.get("index") is not None}
    duration = observed_total = total = 0.0
    observed_steps = 0
    for index, step in enumerate(steps):
        step_sec = float(step.get("duration_sec") or 0.0)
        step_m = float(step.get("distance_m") or 0.0)
        match = by_index.get(index)
        parts = (match or {}).get("links") or []
        if not parts:
            duration += step_sec
            total += step_m
            continue
        # link_match_json은 폴리라인 샘플 길이를 쓰므로 OSRM 거리보다 그 합계를 기준으로 삼습니다.
        step_total = float(match.get("total_m") or step_m or 0.0)
        observed_sec = observed_m = 0.0
        for part in parts:
            observation = observations.get(part.get("link_id"))
            seconds = portion_seconds(part.get("length_m") or 0.0, observation) if observation else None
            if seconds is None:
                continue
            observed_sec += seconds
            observed_m += float(part.get("length_m") or 0.0)
        # 관측이 없는 나머지 길이(미관측 링크·반대 방향·미매칭)는 OSRM 시간을 길이 비례로 유지합니다.
        remainder = max(0.0, 1.0 - observed_m / step_total) if step_total else 1.0
        duration += observed_sec + step_sec * remainder
        observed_total += observed_m
        total += step_total
        if observed_m > 0:
            observed_steps += 1
    return {"duration_sec": duration, "observed_m": observed_total, "total_m": total, "observed_steps": observed_steps}


def quality_grade(total_m, observed_m):
    """관측으로 설명된 길이 비율로 재구성 품질 등급을 정합니다."""
    if not total_m:
        return QUALITY_UNUSABLE
    ratio = observed_m / total_m
    if ratio >= 0.8:
        return "high"
    if ratio >= 0.5:
        return "medium"
    if ratio >= LABEL_MIN_OBSERVED_RATIO:
        return "low"
    return QUALITY_UNUSABLE


def nearest_observation(observations, moment, window):
    """moment에 가장 가까운 관측을 고릅니다. window 밖이면 None."""
    if not observations:
        return None
    best = min(observations, key=lambda item: abs((item["measured_at"] - moment).total_seconds()))
    if abs((best["measured_at"] - moment).total_seconds()) > window.total_seconds():
        return None
    return best


def load_link_observations(db, link_ids, start, end):
    """링크별 속도·통행시간 관측과 링크 길이를 읽습니다. {link_id: [관측...]}"""
    if not link_ids:
        return {}
    rows = db.execute(text("""
        SELECT v.link_id, v.measured_at, v.speed_kmh, v.travel_time_sec, r.geometry_length_m
        FROM traffic_speed_measurements v
        LEFT JOIN road_segments r ON r.link_id = v.link_id
        WHERE v.link_id IN :link_ids
          AND v.measured_at >= :start AND v.measured_at <= :end
        ORDER BY v.link_id, v.measured_at
    """).bindparams(bindparam("link_ids", expanding=True)),
        {"link_ids": list(link_ids), "start": start, "end": end}).mappings()
    by_link = {}
    for row in rows:
        by_link.setdefault(row["link_id"], []).append({
            "measured_at": row["measured_at"],
            "speed_kmh": float(row["speed_kmh"]) if row["speed_kmh"] is not None else None,
            "travel_time_sec": float(row["travel_time_sec"]) if row["travel_time_sec"] is not None else None,
            "length_m": float(row["geometry_length_m"]) if row["geometry_length_m"] is not None else None,
        })
    return by_link


def select_trip_observations(by_link, link_ids, departure_at, osrm_duration_sec, window):
    """주행 중간 시각(출발 + OSRM 시간/2)에 가장 가까운 관측을 링크별로 고릅니다."""
    midpoint = departure_at + timedelta(seconds=float(osrm_duration_sec or 0) / 2)
    selected = {}
    for link_id in link_ids:
        observation = nearest_observation(by_link.get(link_id, []), midpoint, window)
        if observation is not None:
            selected[link_id] = observation
    return selected


def matched_link_ids(link_matches):
    return {part["link_id"] for match in link_matches for part in (match.get("links") or []) if part.get("link_id")}


class RouteDurationReconstructionService:
    def __init__(self, db: Session, window_minutes: int = OBSERVATION_WINDOW_MIN):
        self.db = db
        self.window = timedelta(minutes=window_minutes)

    def reconstruct(self, now: datetime | None = None, limit: int = 500) -> int:
        """출발 시각이 지난 후보의 actual_duration_sec를 재구성해 저장합니다.

        관측이 부족해 라벨을 만들 수 없는 후보는 품질만 `unusable`로 남겨 다시 처리하지 않습니다.
        """
        now = now or datetime.now()
        rows = list(self.db.execute(text("""
            SELECT c.id, c.route_request_id, c.route_id, c.steps_json, c.link_match_json,
                   c.osrm_duration_sec, r.departure_at
            FROM route_request_candidates c
            JOIN route_requests r ON r.route_request_id = c.route_request_id
            WHERE c.actual_duration_sec IS NULL
              AND c.actual_duration_quality IS NULL
              AND c.link_match_json IS NOT NULL
              AND r.departure_at <= :now
            ORDER BY r.departure_at
            LIMIT :limit
        """), {"now": now, "limit": limit}).mappings())
        if not rows:
            return 0
        parsed = [(row, _parse_json(row["steps_json"]) or [], _parse_json(row["link_match_json"]) or []) for row in rows]
        link_ids = set().union(*(matched_link_ids(matches) for _, _, matches in parsed))
        departures = [row["departure_at"] for row in rows]
        longest = max(float(row["osrm_duration_sec"] or 0) for row in rows)
        by_link = load_link_observations(
            self.db, link_ids, min(departures) - self.window,
            max(departures) + timedelta(seconds=longest) + self.window,
        )
        updated = 0
        for row, steps, matches in parsed:
            observations = select_trip_observations(
                by_link, matched_link_ids(matches), row["departure_at"], row["osrm_duration_sec"], self.window,
            )
            result = reconstruct_candidate_duration(steps, matches, observations)
            grade = quality_grade(result["total_m"], result["observed_m"])
            self.db.execute(text("""
                UPDATE route_request_candidates
                SET actual_duration_sec = :duration,
                    actual_duration_quality = :grade,
                    actual_duration_computed_at = :now
                WHERE id = :id
            """), {"duration": round(result["duration_sec"], 2) if grade != QUALITY_UNUSABLE else None,
                   "grade": grade, "now": now, "id": row["id"]})
            updated += 1
        self.db.commit()
        return updated
