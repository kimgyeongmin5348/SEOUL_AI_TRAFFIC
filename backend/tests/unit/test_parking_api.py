from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.services.parking_service import ParkingApiError, SeoulParkingService


def test_nearby_parking_joins_realtime_rows_and_filters_restricted_lots():
    service = SeoulParkingService(api_key="test-key")
    master = [
        {
            "PKLT_CD": "general",
            "PKLT_NM": "시청 공영주차장",
            "ADDR": "서울 중구",
            "LAT": 37.5663,
            "LOT": 126.9780,
            "TPKCT": 20,
            "CHGD_FREE_SE": "Y",
        },
        {
            "PKLT_CD": "general",
            "PKLT_NM": "시청 공영주차장",
            "ADDR": "서울 중구",
            "LAT": 37.5664,
            "LOT": 126.9781,
            "TPKCT": 20,
        },
        {
            "PKLT_CD": "bus",
            "PKLT_NM": "관광버스전용 주차장",
            "ADDR": "서울 중구",
            "LAT": 37.5663,
            "LOT": 126.9780,
            "TPKCT": 10,
        },
    ]
    realtime = [
        {
            "PKLT_CD": "general",
            "TPKCT": 20,
            "NOW_PRK_VHCL_CNT": 7,
            "NOW_PRK_VHCL_UPDT_TM": "2026-09-14 12:00:00",
            "PAY_YN": "Y",
        }
    ]
    service._nearby_from_db = lambda *args, **kwargs: None  # type: ignore[method-assign]
    service._cached_rows = lambda: (master, realtime)  # type: ignore[method-assign]

    result = service.nearby(37.5662952, 126.9779451)

    assert result["source"] == "서울 열린데이터광장"
    assert len(result["lots"]) == 1
    lot = result["lots"][0]
    assert lot["parking_code"] == "general"
    assert lot["available_spaces"] == 13
    assert lot["realtime_status"] == "AVAILABLE"
    assert lot["paid"] is True


def test_nearby_parking_from_db_returns_sorted_lots():
    service = SeoulParkingService(api_key="test-key")
    mock_lots = [
        {
            "parking_code": "db-lot-1",
            "name": "DB 주차장",
            "address": "서울 중구",
            "latitude": 37.5663,
            "longitude": 126.9780,
            "distance_m": 120,
            "capacity": 50,
            "occupied_spaces": 10,
            "available_spaces": 40,
            "realtime_status": "AVAILABLE",
            "observed_at": "2026-09-14T12:00:00",
            "restriction": None,
            "paid": True,
        }
    ]
    service._nearby_from_db = lambda *args, **kwargs: mock_lots  # type: ignore[method-assign]

    result = service.nearby(37.5663, 126.9780)
    assert result["source"] == "RoadPulse DB (Seoul + Geocoded)"
    assert len(result["lots"]) == 1
    assert result["lots"][0]["parking_code"] == "db-lot-1"
    assert result["lots"][0]["available_spaces"] == 40



def test_nearby_parking_endpoint_validates_coordinates_and_hides_upstream_details():
    client = TestClient(app)
    assert client.get("/api/parking/nearby?latitude=0&longitude=0").status_code == 422

    with patch(
        "backend.src.api.app.parking_service.nearby",
        side_effect=ParkingApiError("서울시 주차장 API 호출에 실패했습니다."),
    ):
        response = client.get("/api/parking/nearby?latitude=37.5663&longitude=126.9780")
    assert response.status_code == 503
    assert response.json()["detail"] == "서울시 주차장 API 호출에 실패했습니다."


def test_nearby_parking_endpoint_returns_service_result():
    payload = {
        "source": "서울 열린데이터광장",
        "destination": {"latitude": 37.5663, "longitude": 126.978},
        "radius_m": 1500,
        "queried_at": "2026-09-14T12:00:00+09:00",
        "lots": [],
    }
    with patch("backend.src.api.app.parking_service.nearby", return_value=payload):
        response = TestClient(app).get(
            "/api/parking/nearby?latitude=37.5663&longitude=126.978&limit=8"
        )
    assert response.status_code == 200
    assert response.json() == payload
