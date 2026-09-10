from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from backend.src.api.app import app, get_db, _hash_password, _verify_password


def test_password_hash_is_salted_and_verifiable():
    first = _hash_password("correct horse battery staple")
    second = _hash_password("correct horse battery staple")
    assert first != second
    assert _verify_password("correct horse battery staple", first)
    assert not _verify_password("wrong password", first)
    assert "correct horse" not in first


def test_favorites_require_login():
    client = TestClient(app)
    assert client.get("/api/routes/favorites").status_code == 401
    assert client.post("/api/routes/search", json={"origin": "합정", "destination": "강남"}).status_code == 401


def test_prediction_departure_is_limited_to_three_hours():
    app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        departure = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        response = TestClient(app).post("/api/routes/predict", json={
            "departure_at": departure,
            "candidates": [{
                "id": "A", "duration_sec": 60,
                "steps": [{"name": "테헤란로", "duration_sec": 60}],
            }],
        })
        assert response.status_code == 422
        assert "3시간" in response.text
    finally:
        app.dependency_overrides.clear()
