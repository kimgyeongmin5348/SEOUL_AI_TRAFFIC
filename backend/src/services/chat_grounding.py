"""Build a small, traceable RoadPulse data context for chatbot answers."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.src.services.route_prediction import predict_spot_series

KST = timezone(timedelta(hours=9))
_ROAD_TERM = re.compile(r"[0-9A-Za-z가-힣]+(?:대로|로|길)")
_RAIN_TERMS = ("비", "강수", "우천", "rain")
_HISTORY_TERMS = ("때", "영향", "변화", "차이", "비교", "평균", "평소", "과거", "이력")

# 자주 쓰이는 도로명 축약어 및 오타 매핑
ROAD_ALIASES: dict[str, list[str]] = {
    "올림대로": ["올림픽대로"],
    "올림픽": ["올림픽대로", "올림픽로"],
    "강변": ["강변북로"],
    "내부순환": ["내부순환로"],
    "동부간선": ["동부간선도로"],
    "서부간선": ["서부간선도로"],
    "북부간선": ["북부간선도로"],
    "남부순환": ["남부순환로"],
    "분당수서": ["분당수서로", "분당수서간도시고속화도로"],
}


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(tzinfo=KST).isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _matches_question(name: str, question: str, terms: set[str]) -> bool:
    normalized_name = _normalize(name)
    normalized_question = _normalize(question)
    if normalized_name and (normalized_name in normalized_question or normalized_question in normalized_name):
        return True
    return any(len(term) >= 2 and (term in normalized_name or normalized_name in term) for term in terms)


def _asks_historical_rain_impact(question: str) -> bool:
    """Return whether the user is asking to compare traffic under rain/dry conditions."""
    normalized = question.lower()
    asks_about_rain = any(term in normalized for term in _RAIN_TERMS)
    asks_about_traffic = "교통" in normalized or "통행량" in normalized
    asks_for_comparison = any(term in normalized for term in _HISTORY_TERMS)
    return asks_about_rain and asks_about_traffic and asks_for_comparison


def _representative_spots(spots: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    """Select a deterministic spread of spot IDs for a city-wide quick comparison."""
    ordered = sorted(spots, key=lambda row: str(row["spot_id"]))
    if len(ordered) <= limit:
        return ordered
    return [ordered[index * len(ordered) // limit] for index in range(limit)]


def _historical_rain_impact(db, *, start: datetime, end: datetime, spot_ids: list[str]) -> dict[str, Any] | None:
    """Compare rainy and dry traffic observations within the same weekday/hour strata.

    Matching by spot, direction, lane, weekday and hour keeps the result from simply
    comparing (for example) rainy weekends with dry rush hours.  KMA uses NULL for
    hours without recorded precipitation, which the training pipeline also treats
    as 0 mm.
    """
    spot_filter = ""
    params: dict[str, Any] = {"start": start, "end": end}
    if spot_ids:
        placeholders = []
        for index, spot_id in enumerate(spot_ids):
            key = f"spot_id_{index}"
            placeholders.append(f":{key}")
            params[key] = spot_id
        spot_filter = f"AND v.spot_id IN ({', '.join(placeholders)})"

    weather_period = db.execute(text("""
        SELECT MIN(observed_at) AS period_start,
               MAX(observed_at) AS period_end,
               SUM(COALESCE(rainfall_mm, 0)>0) AS rainy_hours,
               SUM(COALESCE(rainfall_mm, 0)=0) AS dry_hours
        FROM weather_measurements
        WHERE weather_station_id='108'
          AND observed_at>=:start AND observed_at<:end
    """), params).mappings().first()

    row = db.execute(text(f"""
        WITH comparable AS (
            SELECT v.spot_id, v.direction_code, v.lane_no,
                   HOUR(v.measured_at) AS hour_of_day,
                   WEEKDAY(v.measured_at) AS day_of_week,
                   AVG(CASE WHEN COALESCE(w.rainfall_mm, 0)>0
                            THEN v.traffic_volume END) AS rainy_avg,
                   AVG(CASE WHEN COALESCE(w.rainfall_mm, 0)=0
                            THEN v.traffic_volume END) AS dry_avg,
                   SUM(COALESCE(w.rainfall_mm, 0)>0) AS rainy_samples,
                   SUM(COALESCE(w.rainfall_mm, 0)=0) AS dry_samples
            FROM traffic_volume_measurements v
            JOIN weather_measurements w
              ON w.weather_station_id='108' AND w.observed_at=v.measured_at
            WHERE v.measured_at>=:start AND v.measured_at<:end
              {spot_filter}
            GROUP BY v.spot_id, v.direction_code, v.lane_no,
                     HOUR(v.measured_at), WEEKDAY(v.measured_at)
            HAVING rainy_samples>0 AND dry_samples>0
        )
        SELECT SUM(rainy_samples) AS rainy_samples,
               SUM(dry_samples) AS dry_samples,
               AVG(rainy_avg) AS rainy_avg_volume,
               AVG(dry_avg) AS dry_avg_volume,
               AVG((rainy_avg-dry_avg)/NULLIF(dry_avg, 0)*100) AS average_change_pct
        FROM comparable
    """), params).mappings().first()
    if not row or row.get("rainy_samples") is None or row.get("dry_samples") is None:
        return None

    result = {
        key: _serialize(value)
        for source in (dict(weather_period or {}), dict(row))
        for key, value in source.items()
    }
    for key in ("rainy_avg_volume", "dry_avg_volume", "average_change_pct"):
        if result.get(key) is not None:
            result[key] = round(float(result[key]), 1)
    result["rain_definition"] = "rainfall_mm > 0; NULL은 학습 전처리와 동일하게 0 mm로 처리"
    result["comparison_method"] = "같은 측정지점·방향·차로·요일·시간대끼리 비교한 관측 평균"
    result["sample_unit"] = "차로·시간"
    return result


def build_chat_grounding(db, messages: list[dict[str, str]], now: datetime | None = None) -> dict[str, Any]:
    """Collect observations and trained-model forecasts relevant to the last question.

    The returned object is intentionally compact so it can be supplied to the LLM
    verbatim and shown to the user as traceability metadata.
    """
    clock = now or datetime.now(KST)
    naive_now = clock.astimezone(KST).replace(tzinfo=None)
    recent_user_text = " ".join(
        m.get("content", "") for m in messages[-8:] if m.get("role") == "user"
    )
    terms = {_normalize(term) for term in _ROAD_TERM.findall(recent_user_text)}
    normalized_user_text = _normalize(recent_user_text)
    for alias, targets in ROAD_ALIASES.items():
        if _normalize(alias) in normalized_user_text:
            for target in targets:
                terms.add(_normalize(target))

    result: dict[str, Any] = {
        "grounded": False,
        "queried_at": clock.astimezone(KST).isoformat(),
        "matched_roads": [],
        "current_speeds": [],
        "weather": None,
        "active_incidents": [],
        "model_forecasts": [],
        "historical_rain_impact": None,
        "sources": [],
        "warnings": [],
    }

    try:
        spots = list(
            db.execute(text("SELECT spot_id, spot_name FROM traffic_spots ORDER BY spot_name"))
            .mappings()
            .all()
        )
        matched_spots = [
            dict(row)
            for row in spots
            if _matches_question(str(row["spot_name"]), recent_user_text, terms)
        ][:3]

        speed_rows = list(
            db.execute(text("""
                SELECT r.road_name, ROUND(AVG(s.speed_kmh), 1) AS avg_speed_kmh,
                       MAX(s.measured_at) AS measured_at, COUNT(*) AS segment_count
                FROM traffic_speed_measurements s
                JOIN road_segments r ON r.link_id=s.link_id
                WHERE s.measured_at >= (SELECT MAX(measured_at) - INTERVAL 7 MINUTE FROM traffic_speed_measurements)
                  AND r.road_name IS NOT NULL AND r.road_name != ''
                GROUP BY r.road_name
                ORDER BY avg_speed_kmh ASC
            """))
            .mappings()
            .all()
        )
        matched_speeds = [
            dict(row)
            for row in speed_rows
            if _matches_question(str(row["road_name"]), recent_user_text, terms)
        ]
        selected_speeds = matched_speeds[:10] if (terms or matched_spots) else [dict(r) for r in speed_rows[:8]]
        result["current_speeds"] = [
            {key: _serialize(value) for key, value in row.items()} for row in selected_speeds
        ]
        if selected_speeds:
            result["sources"].append("서울시 TrafficInfo 실시간 도로 속도")

        weather = db.execute(text("""
            SELECT s.station_name, w.observed_at, w.temperature_c, w.rainfall_mm,
                   w.humidity_pct, w.wind_speed_ms
            FROM weather_measurements w
            JOIN weather_stations s ON s.weather_station_id=w.weather_station_id
            ORDER BY w.observed_at DESC LIMIT 1
        """)).mappings().first()
        if weather:
            result["weather"] = {key: _serialize(value) for key, value in dict(weather).items()}
            result["sources"].append("기상청 관측")

        incidents = list(db.execute(text("""
            SELECT i.incident_type, i.description, i.occurred_at, i.expected_clear_at,
                   r.road_name
            FROM incidents i
            LEFT JOIN road_segments r ON r.link_id=i.link_id
            WHERE (i.expected_clear_at IS NULL OR i.expected_clear_at>:now)
              AND i.occurred_at>=:start
            ORDER BY i.occurred_at DESC LIMIT 20
        """), {"now": naive_now, "start": naive_now - timedelta(hours=24)}).mappings().all())
        relevant_incidents = [
            dict(row)
            for row in incidents
            if not terms
            or (row.get("road_name") and _matches_question(str(row["road_name"]), recent_user_text, terms))
            or _matches_question(str(row.get("description") or ""), recent_user_text, terms)
        ][:8]
        result["active_incidents"] = [
            {key: _serialize(value) for key, value in row.items()} for row in relevant_incidents
        ]
        if relevant_incidents:
            result["sources"].append("서울시 AccInfo 돌발정보")

        matched_names = {
            str(row["spot_name"]) for row in matched_spots
        } | {str(row["road_name"]) for row in matched_speeds}
        result["matched_roads"] = sorted(matched_names)

        for spot in matched_spots:
            try:
                forecast = predict_spot_series(db, str(spot["spot_id"]), clock, horizon_hours=3)
                result["model_forecasts"].append(forecast)
            except ValueError as exc:
                result["warnings"].append(f"{spot['spot_name']} 예측 불가: {exc}")
        if result["model_forecasts"]:
            result["sources"].append("RoadPulse 학습 모델 교통량 예측")

        if _asks_historical_rain_impact(recent_user_text):
            history_start = naive_now - timedelta(days=730)
            history_spots = matched_spots or _representative_spots(spots)
            impact = _historical_rain_impact(
                db,
                start=history_start,
                end=naive_now,
                spot_ids=[str(row["spot_id"]) for row in history_spots],
            )
            if impact:
                impact["scope"] = "질문에서 매칭된 측정지점" if matched_spots else "서울 전역 대표 측정지점 표본"
                impact["spot_count"] = len(history_spots)
                impact["spots"] = [
                    {"spot_id": str(row["spot_id"]), "spot_name": str(row["spot_name"])}
                    for row in history_spots
                ]
                result["historical_rain_impact"] = impact
                result["sources"].append("RoadPulse 2년치 교통량·기상 관측 이력")
            else:
                result["warnings"].append("비/무강수 교통량을 함께 비교할 수 있는 이력 표본이 부족합니다.")

        result["grounded"] = bool(
            result["current_speeds"]
            or result["weather"]
            or result["active_incidents"]
            or result["model_forecasts"]
            or result["historical_rain_impact"]
        )
        return result
    except SQLAlchemyError:
        db.rollback()
        result["warnings"].append("RoadPulse DB를 조회하지 못했습니다.")
        return result
