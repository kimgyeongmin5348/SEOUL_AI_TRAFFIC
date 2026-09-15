"""경로 추천 요청과 OSRM 후보 경로를 로그 테이블에 저장합니다.

경로 단위 학습 데이터셋(route_request_id 단위 후보 순위 학습)의 원천이 되므로,
추천 성공뿐 아니라 보류(ValueError) 요청도 후보 경로와 함께 남깁니다.
로그 저장 실패가 추천 응답 자체를 실패시키지 않도록 예외는 삼키고 경고만 남깁니다.
"""
import json
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.src.services.route_prediction import determine_route_direction

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"   # 후보는 있었지만 AI 추천이 보류됨 (ValueError)


def _naive_kst(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=None)


def _endpoint(candidates, index):
    """후보 polyline의 첫/마지막 좌표(lng, lat)를 출발지·목적지 좌표로 사용합니다."""
    for candidate in candidates:
        if candidate.coordinates:
            lng, lat = candidate.coordinates[index]
            return float(lat), float(lng)
    return None, None


def build_request_row(request_id, req, now, departure, recommendation=None, error=None):
    candidates = req.candidates
    origin = getattr(req, "origin", None)
    destination = getattr(req, "destination", None)
    origin_lat, origin_lng = (origin.lat, origin.lng) if origin else _endpoint(candidates, 0)
    dest_lat, dest_lng = (destination.lat, destination.lng) if destination else _endpoint(candidates, -1)
    comparison = (recommendation or {}).get("osrm_comparison") or {}
    return {
        "route_request_id": request_id,
        "requested_at": _naive_kst(now),
        "departure_at": _naive_kst(departure),
        "target_at": _naive_kst((recommendation or {}).get("target_at")),
        "origin_name": origin.name if origin else None,
        "origin_lat": origin_lat,
        "origin_lng": origin_lng,
        "destination_name": destination.name if destination else None,
        "destination_lat": dest_lat,
        "destination_lng": dest_lng,
        "candidate_count": len(candidates),
        "status": STATUS_OK if recommendation is not None else STATUS_UNAVAILABLE,
        "status_message": (recommendation or {}).get("message") if recommendation is not None else (error or "")[:500],
        "model_version": (recommendation or {}).get("model_version"),
        "ai_available": bool((recommendation or {}).get("available")),
        "ai_selected_route_id": comparison.get("ai_selected_route_id"),
        "osrm_default_route_id": comparison.get("osrm_default_route_id"),
        "traffic_observed_at": _naive_kst((recommendation or {}).get("observed_at")),
        "weather_observed_at": _naive_kst((recommendation or {}).get("weather_at")),
        "forecast_steps": (recommendation or {}).get("forecast_steps"),
    }


def build_candidate_rows(request_id, candidates, recommendation=None):
    results = {route["id"]: route for route in (recommendation or {}).get("routes", [])}
    rows = []
    for candidate in candidates:
        result = results.get(candidate.id, {})
        rows.append({
            "route_request_id": request_id,
            "route_id": candidate.id,
            "route_distance_m": candidate.distance_m,
            "osrm_duration_sec": candidate.duration_sec,
            "segment_count": len(candidate.steps),
            "route_direction_code": determine_route_direction(candidate.coordinates) if candidate.coordinates else None,
            "score": result.get("score"),
            "traffic_penalty_sec": result.get("traffic_penalty_sec"),
            "incident_penalty_sec": result.get("incident_penalty_sec"),
            "speed_penalty_sec": result.get("speed_penalty_sec"),
            "coverage": result.get("coverage"),
            "match_ratio": result.get("match_ratio"),
            "speed_match_ratio": result.get("speed_match_ratio"),
            "link_match_ratio": result.get("link_match_ratio"),
            "direction_match_ratio": result.get("direction_match_ratio"),
            "direction_matched_steps": result.get("direction_matched_steps"),
            "incident_count": result.get("incident_count"),
            "predicted_volume": result.get("predicted_volume"),
            "typical_volume": result.get("typical_volume"),
            "ai_selected": bool(result.get("ai")),
            # 이후 링크 map-match와 actual_duration_sec 재구성에 원본 구간·좌표가 필요합니다.
            "steps_json": json.dumps(
                [{"name": s.name, "duration_sec": s.duration_sec, "distance_m": s.distance_m} for s in candidate.steps],
                ensure_ascii=False,
            ),
            "coordinates_json": json.dumps(candidate.coordinates) if candidate.coordinates else None,
            # step별 링크 map-match 결과(매칭 link_id, 거리, 방위차, 방향 일치 여부)를 보존합니다.
            "link_match_json": json.dumps(result.get("link_match_details"), ensure_ascii=False)
            if result.get("link_match_details") else None,
        })
    return rows


INSERT_REQUEST = text("""
    INSERT INTO route_requests (
        route_request_id, requested_at, departure_at, target_at,
        origin_name, origin_lat, origin_lng, destination_name, destination_lat, destination_lng,
        candidate_count, status, status_message, model_version, ai_available,
        ai_selected_route_id, osrm_default_route_id, traffic_observed_at, weather_observed_at, forecast_steps
    ) VALUES (
        :route_request_id, :requested_at, :departure_at, :target_at,
        :origin_name, :origin_lat, :origin_lng, :destination_name, :destination_lat, :destination_lng,
        :candidate_count, :status, :status_message, :model_version, :ai_available,
        :ai_selected_route_id, :osrm_default_route_id, :traffic_observed_at, :weather_observed_at, :forecast_steps
    )
""")

INSERT_CANDIDATE = text("""
    INSERT INTO route_request_candidates (
        route_request_id, route_id, route_distance_m, osrm_duration_sec, segment_count, route_direction_code,
        score, traffic_penalty_sec, incident_penalty_sec, speed_penalty_sec,
        coverage, match_ratio, speed_match_ratio, link_match_ratio,
        direction_match_ratio, direction_matched_steps,
        incident_count, predicted_volume, typical_volume,
        ai_selected, steps_json, coordinates_json, link_match_json
    ) VALUES (
        :route_request_id, :route_id, :route_distance_m, :osrm_duration_sec, :segment_count, :route_direction_code,
        :score, :traffic_penalty_sec, :incident_penalty_sec, :speed_penalty_sec,
        :coverage, :match_ratio, :speed_match_ratio, :link_match_ratio,
        :direction_match_ratio, :direction_matched_steps,
        :incident_count, :predicted_volume, :typical_volume,
        :ai_selected, :steps_json, :coordinates_json, :link_match_json
    )
""")


def log_route_request(db, request_id, req, now, departure, recommendation=None, error=None):
    """요청 1행과 후보 N행을 저장합니다. 실패해도 예외를 밖으로 내지 않고 False를 반환합니다."""
    try:
        db.execute(INSERT_REQUEST, build_request_row(request_id, req, now, departure, recommendation, error))
        db.execute(INSERT_CANDIDATE, build_candidate_rows(request_id, req.candidates, recommendation))
        db.commit()
        return True
    except SQLAlchemyError:
        logger.warning("Route request log skipped for %s", request_id, exc_info=True)
        try:
            db.rollback()
        except SQLAlchemyError:
            pass
        return False
