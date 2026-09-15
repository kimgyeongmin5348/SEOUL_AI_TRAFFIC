"""경로 후보의 actual_duration_sec를 링크 관측 통행시간으로 재구성합니다.

실제 주행 이력이 없으므로, OSRM step을 링크 기하에 map-match한 결과(link_match_json)와
출발 시각 전후의 traffic_speed_measurements.travel_time_sec를 결합해 경로 통행시간을
재구성합니다. 관측이 없는 step은 OSRM 시간을 그대로 사용하고, 재구성 신뢰도를
품질 등급(high/medium/low)으로 남겨 학습 라벨의 한계를 숨기지 않습니다.
"""

import json
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

# 출발 시각과 관측 시각의 허용 차이(분). 이보다 멀면 해당 링크 관측을 쓰지 않습니다.
OBSERVATION_WINDOW_MIN = 60


def _parse_json(value):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    return json.loads(value)


def reconstruct_candidate_duration(steps, link_matches, travel_times):
    """step별 OSRM 시간과 링크 관측 통행시간을 결합해 경로 통행시간을 재구성합니다.

    steps: [{"name", "duration_sec", "distance_m"}, ...]
    link_matches: [{"index", "link_id", "direction_match", ...}, ...]
    travel_times: {link_id: travel_time_sec}
    반환: (actual_duration_sec, observed_steps, matched_steps)
    """
    by_index = {m["index"]: m for m in link_matches if m.get("index") is not None}
    total = 0.0
    observed_steps = 0
    matched_steps = 0
    for index, step in enumerate(steps):
        match = by_index.get(index)
        link_id = match.get("link_id") if match else None
        if link_id:
            matched_steps += 1
            observed = travel_times.get(link_id)
            if observed is not None:
                total += float(observed)
                observed_steps += 1
                continue
        total += float(step.get("duration_sec") or 0.0)
    return total, observed_steps, matched_steps


def quality_grade(step_count, matched_steps, observed_steps):
    """링크 매칭률과 관측 사용률로 재구성 품질 등급을 정합니다."""
    if not step_count:
        return "low"
    match_ratio = matched_steps / step_count
    observed_ratio = observed_steps / step_count
    if match_ratio >= 0.8 and observed_ratio >= 0.8:
        return "high"
    if match_ratio >= 0.5 and observed_ratio >= 0.3:
        return "medium"
    return "low"


class RouteDurationReconstructionService:
    def __init__(self, db: Session, window_minutes: int = OBSERVATION_WINDOW_MIN):
        self.db = db
        self.window = timedelta(minutes=window_minutes)

    def reconstruct(self, now: datetime | None = None, limit: int = 500) -> int:
        """출발 시각이 지난 후보의 actual_duration_sec를 재구성해 저장합니다."""
        now = now or datetime.now()
        rows = list(self.db.execute(text("""
            SELECT c.id, c.route_request_id, c.route_id, c.steps_json, c.link_match_json,
                   r.departure_at
            FROM route_request_candidates c
            JOIN route_requests r ON r.route_request_id = c.route_request_id
            WHERE c.actual_duration_sec IS NULL
              AND c.link_match_json IS NOT NULL
              AND r.departure_at <= :now
            ORDER BY r.departure_at
            LIMIT :limit
        """), {"now": now, "limit": limit}).mappings())
        if not rows:
            return 0
        parsed = []
        link_ids = set()
        for row in rows:
            steps = _parse_json(row["steps_json"]) or []
            matches = _parse_json(row["link_match_json"]) or []
            parsed.append((row, steps, matches))
            for match in matches:
                if match.get("link_id"):
                    link_ids.add(match["link_id"])
        travel_times = self._load_travel_times(link_ids, rows)
        updated = 0
        for row, steps, matches in parsed:
            departure = row["departure_at"]
            times = {}
            for match in matches:
                link_id = match.get("link_id")
                if not link_id:
                    continue
                value = self._nearest_travel_time(travel_times.get(link_id, []), departure)
                if value is not None:
                    times[link_id] = value
            duration, observed_steps, matched_steps = reconstruct_candidate_duration(steps, matches, times)
            grade = quality_grade(len(steps), matched_steps, observed_steps)
            self.db.execute(text("""
                UPDATE route_request_candidates
                SET actual_duration_sec = :duration,
                    actual_duration_quality = :grade,
                    actual_duration_computed_at = :now
                WHERE id = :id
            """), {"duration": round(duration, 2), "grade": grade, "now": now, "id": row["id"]})
            updated += 1
        self.db.commit()
        return updated

    def _load_travel_times(self, link_ids, rows):
        if not link_ids:
            return {}
        departures = [row["departure_at"] for row in rows]
        start = min(departures) - self.window
        end = max(departures) + self.window
        result = self.db.execute(text("""
            SELECT link_id, measured_at, travel_time_sec
            FROM traffic_speed_measurements
            WHERE link_id IN :link_ids
              AND measured_at >= :start AND measured_at <= :end
            ORDER BY link_id, measured_at
        """).bindparams(bindparam("link_ids", expanding=True)),
            {"link_ids": list(link_ids), "start": start, "end": end}).mappings()
        by_link = {}
        for row in result:
            by_link.setdefault(row["link_id"], []).append(
                (row["measured_at"], float(row["travel_time_sec"]))
            )
        return by_link

    def _nearest_travel_time(self, observations, departure):
        if not observations:
            return None
        best = min(observations, key=lambda item: abs((item[0] - departure).total_seconds()))
        if abs((best[0] - departure).total_seconds()) > self.window.total_seconds():
            return None
        return best[1]