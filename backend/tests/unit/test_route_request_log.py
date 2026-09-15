import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from backend.src.api.app import RoutePredictionRequest, app
from backend.src.db.database import get_db
from backend.src.services.route_request_log import (
    STATUS_OK,
    STATUS_UNAVAILABLE,
    build_candidate_rows,
    build_request_row,
    log_route_request,
)

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 15, 8, 30, tzinfo=KST)


def request(**extra):
    return RoutePredictionRequest(candidates=[
        dict(id="A", duration_sec=600, distance_m=5000,
             coordinates=[[126.90, 37.50], [126.95, 37.55]],
             steps=[dict(name="강남대로", duration_sec=400, distance_m=3000),
                    dict(name="테헤란로", duration_sec=200, distance_m=2000)]),
        dict(id="B", duration_sec=700, steps=[dict(name="올림픽대로", duration_sec=700)]),
    ], **extra)


def recommendation():
    return {
        "model_version": "traffic_xgb_baseline_v1", "available": True,
        "target_at": "2026-09-15T09:00:00+09:00", "observed_at": "2026-09-15T07:00:00+09:00",
        "weather_at": "2026-09-15T08:00:00+09:00", "forecast_steps": 2, "message": "ok",
        "osrm_comparison": {"osrm_default_route_id": "A", "ai_selected_route_id": "B"},
        "routes": [
            {"id": "A", "ai": False, "score": 700.5, "coverage": 1.0, "match_ratio": 1.0,
             "traffic_penalty_sec": 100.5, "incident_penalty_sec": 0, "speed_penalty_sec": 0,
             "speed_match_ratio": 0.5, "incident_count": 0, "predicted_volume": 1200.0, "typical_volume": 1000.0},
            {"id": "B", "ai": True, "score": 690.0, "coverage": 1.0, "match_ratio": 1.0,
             "traffic_penalty_sec": 0, "incident_penalty_sec": 0, "speed_penalty_sec": 0,
             "speed_match_ratio": 0, "incident_count": 1, "predicted_volume": 800.0, "typical_volume": 900.0},
        ],
    }


def test_request_row_keeps_request_identity_and_data_quality():
    req = request(origin=dict(name="서울역", lat=37.5547, lng=126.9707),
                  destination=dict(name="강남역", lat=37.4979, lng=127.0276))
    row = build_request_row("rid", req, NOW, NOW + timedelta(minutes=30), recommendation())
    assert row["status"] == STATUS_OK and row["ai_available"] is True
    assert row["requested_at"] == datetime(2026, 9, 15, 8, 30)
    assert row["departure_at"] == datetime(2026, 9, 15, 9, 0)
    assert row["target_at"] == datetime(2026, 9, 15, 9, 0)
    assert row["traffic_observed_at"] == datetime(2026, 9, 15, 7, 0)
    assert row["origin_name"] == "서울역" and row["destination_lng"] == 127.0276
    assert row["ai_selected_route_id"] == "B" and row["osrm_default_route_id"] == "A"
    assert row["candidate_count"] == 2 and row["forecast_steps"] == 2


def test_request_row_falls_back_to_polyline_endpoints_when_places_missing():
    row = build_request_row("rid", request(), NOW, NOW, recommendation())
    assert row["origin_name"] is None
    assert (row["origin_lat"], row["origin_lng"]) == (37.50, 126.90)
    assert (row["destination_lat"], row["destination_lng"]) == (37.55, 126.95)


def test_unavailable_request_is_logged_with_reason_and_raw_candidates():
    req = request()
    row = build_request_row("rid", req, NOW, NOW, error="교통량 관측이 3시간 이상 지연되어 AI 추천을 보류했습니다.")
    assert row["status"] == STATUS_UNAVAILABLE and "지연" in row["status_message"]
    assert row["model_version"] is None and row["ai_available"] is False
    rows = build_candidate_rows("rid", req.candidates)
    assert [r["route_id"] for r in rows] == ["A", "B"]
    assert rows[0]["score"] is None and rows[0]["ai_selected"] is False
    assert rows[0]["osrm_duration_sec"] == 600 and rows[0]["segment_count"] == 2


def test_candidate_rows_store_scores_and_raw_geometry_for_label_reconstruction():
    req = request()
    rows = {r["route_id"]: r for r in build_candidate_rows("rid", req.candidates, recommendation())}
    assert rows["B"]["ai_selected"] is True and rows["A"]["ai_selected"] is False
    assert rows["A"]["score"] == 700.5 and rows["A"]["traffic_penalty_sec"] == 100.5
    assert rows["A"]["route_distance_m"] == 5000 and rows["B"]["route_distance_m"] is None
    steps = json.loads(rows["A"]["steps_json"])
    assert steps[0] == {"name": "강남대로", "duration_sec": 400, "distance_m": 3000}
    assert json.loads(rows["A"]["coordinates_json"]) == [[126.90, 37.50], [126.95, 37.55]]
    assert rows["B"]["coordinates_json"] is None and rows["B"]["route_direction_code"] is None
    # 서울시청 방향으로 향하는 polyline은 도심 유입(1)으로 판정됩니다.
    assert rows["A"]["route_direction_code"] == 1


def test_log_failure_does_not_raise_and_rolls_back():
    db = MagicMock()
    db.execute.side_effect = OperationalError("insert", {}, Exception("down"))
    assert log_route_request(db, "rid", request(), NOW, NOW, recommendation()) is False
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_api_logs_successful_and_unavailable_requests():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    body = {"candidates": [dict(id="A", duration_sec=600, steps=[dict(name="강남대로", duration_sec=600)])],
            "origin": {"name": "서울역", "lat": 37.5547, "lng": 126.9707}}
    try:
        client = TestClient(app)
        with patch("backend.src.api.app.predict_routes", return_value=recommendation()), \
             patch("backend.src.api.app.explain_route_recommendation", return_value="설명"), \
             patch("backend.src.api.app.log_route_request") as logger:
            response = client.post("/api/routes/predict", json=body)
            assert response.status_code == 200
            request_id = response.json()["route_request_id"]
            assert len(request_id) == 36
            logger.assert_called_once()
            assert logger.call_args.args[1] == request_id
            assert logger.call_args.args[2].origin.name == "서울역"
            assert logger.call_args.args[5]["route_request_id"] == request_id
        with patch("backend.src.api.app.predict_routes", side_effect=ValueError("AI 추천을 보류했습니다.")), \
             patch("backend.src.api.app.log_route_request") as logger:
            response = client.post("/api/routes/predict", json=body)
            assert response.status_code == 503
            logger.assert_called_once()
            assert logger.call_args.kwargs["error"] == "AI 추천을 보류했습니다."
    finally:
        app.dependency_overrides.clear()
