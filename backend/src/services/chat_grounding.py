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
    if normalized_name and normalized_name in normalized_question:
        return True
    return any(len(term) >= 2 and term in normalized_name for term in terms)


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
    result: dict[str, Any] = {
        "grounded": False,
        "queried_at": clock.astimezone(KST).isoformat(),
        "matched_roads": [],
        "current_speeds": [],
        "weather": None,
        "active_incidents": [],
        "model_forecasts": [],
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
                WHERE s.measured_at=(SELECT MAX(measured_at) FROM traffic_speed_measurements)
                  AND r.road_name IS NOT NULL AND r.road_name != ''
                GROUP BY r.road_name
                ORDER BY avg_speed_kmh ASC
                LIMIT 500
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

        result["grounded"] = bool(
            result["current_speeds"]
            or result["weather"]
            or result["active_incidents"]
            or result["model_forecasts"]
        )
        return result
    except SQLAlchemyError:
        db.rollback()
        result["warnings"].append("RoadPulse DB를 조회하지 못했습니다.")
        return result
