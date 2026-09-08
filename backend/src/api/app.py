"""Read-only snapshots: observations are KST; DB-generated timestamps are UTC."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.src.db.database import get_db

app = FastAPI(title="RoadPulse")
KST = timezone(timedelta(hours=9))

# Identifiers are fixed here; no SQL identifiers come from request input.
DATASETS = {
    "traffic": ("traffic_volume_measurements", "measured_at", """
        SELECT s.spot_name, v.spot_id, v.measured_at, v.direction_code,
               SUM(v.traffic_volume) AS traffic_volume, MAX(v.collected_at) AS collected_at
        FROM traffic_volume_measurements v JOIN traffic_spots s ON s.spot_id=v.spot_id
        WHERE v.measured_at=:latest
        GROUP BY s.spot_name, v.spot_id, v.measured_at, v.direction_code
        ORDER BY v.spot_id, v.direction_code LIMIT 500
    """),
    "speed": ("traffic_speed_measurements", "measured_at", """
        SELECT r.road_name, s.link_id, s.measured_at, s.speed_kmh, s.travel_time_sec, s.collected_at
        FROM traffic_speed_measurements s LEFT JOIN road_segments r ON r.link_id=s.link_id
        WHERE s.measured_at=:latest ORDER BY s.link_id LIMIT 500
    """),
    "weather": ("weather_measurements", "observed_at", """
        SELECT s.station_name, w.weather_station_id, w.observed_at, w.temperature_c,
               w.rainfall_mm, w.humidity_pct, w.wind_speed_ms, w.pressure_hpa, w.collected_at
        FROM weather_measurements w JOIN weather_stations s ON s.weather_station_id=w.weather_station_id
        WHERE w.observed_at >= :start AND w.observed_at <= :latest
        ORDER BY w.observed_at DESC, w.weather_station_id LIMIT 500
    """),
    "incidents": ("incidents", "collected_at", """
        SELECT incident_id, incident_type, description, occurred_at, expected_clear_at, collected_at
        FROM incidents WHERE collected_at >= :start AND collected_at <= :latest
        ORDER BY collected_at DESC, incident_id LIMIT 500
    """),
    "prediction": ("traffic_predictions", "predicted_at", """
        SELECT p.spot_id, s.spot_name, p.direction_code, p.model_version, p.predicted_at,
               p.target_at, p.predicted_volume, p.actual_volume
        FROM traffic_predictions p JOIN traffic_spots s ON s.spot_id=p.spot_id
        WHERE p.predicted_at=:latest ORDER BY p.target_at, p.spot_id LIMIT 500
    """),
}


def serialize(value, tz=KST):
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz).isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


@app.get("/api/data/{dataset}")
def get_dataset(dataset: str, db: Session = Depends(get_db)):
    if dataset not in DATASETS:
        raise HTTPException(404, "지원하지 않는 데이터입니다.")
    table, clock, query = DATASETS[dataset]
    try:
        latest = db.execute(text(f"SELECT MAX({clock}) FROM {table}")).scalar()
        rows = []
        if latest:
            start = latest.replace(hour=0, minute=0, second=0, microsecond=0)
            if clock == "collected_at":
                start = (latest + timedelta(hours=9)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=9)
            rows = [dict(row) for row in db.execute(text(query), {"latest": latest, "start": start}).mappings()]
        return {
            "source": "DB", "mode": "snapshot",
            "latest_at": serialize(latest, timezone.utc if clock in ("collected_at", "predicted_at") else KST),
            "queried_at": datetime.now(KST).isoformat(),
            "rows": [{key: serialize(value, timezone.utc if key in ("collected_at", "predicted_at") else KST) for key, value in row.items()} for row in rows],
            "limit": 500,
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "DB 조회에 실패했습니다. 연결 설정과 DB 상태를 확인해 주세요.") from None

from pydantic import BaseModel


class RouteSearchRequest(BaseModel):
    origin: str
    destination: str
    label: str | None = None


@app.get("/api/routes/favorites")
def get_favorite_routes(db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT id, origin, destination, label, search_count, 
                   COALESCE(avg_time_min, 35) AS avg_time_min,
                   COALESCE(current_time_min, 40) AS current_time_min,
                   last_searched_at
            FROM route_searches
            ORDER BY search_count DESC, last_searched_at DESC
            LIMIT 4
        """)
        rows = [dict(row) for row in db.execute(query).mappings()]
        return {
            "source": "DB",
            "routes": [
                {
                    "id": row["id"],
                    "origin": row["origin"],
                    "destination": row["destination"],
                    "from": row["origin"],
                    "to": row["destination"],
                    "label": row["label"] or f"{row['origin'].split()[-1]} → {row['destination'].split()[-1]}",
                    "search_count": row["search_count"],
                    "currentTime": row["current_time_min"],
                    "avgTime": row["avg_time_min"],
                    "delta": row["current_time_min"] - row["avg_time_min"],
                    "status": "red" if (row["current_time_min"] - row["avg_time_min"]) > 10 else "yellow" if (row["current_time_min"] - row["avg_time_min"]) > 0 else "green",
                    "last_searched_at": serialize(row["last_searched_at"]),
                }
                for row in rows
            ]
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "즐겨찾기 경로 조회에 실패했습니다.") from None


@app.post("/api/routes/search")
def record_route_search(req: RouteSearchRequest, db: Session = Depends(get_db)):
    if not req.origin.strip() or not req.destination.strip():
        raise HTTPException(400, "출발지와 도착지를 입력해 주세요.")
    try:
        origin_clean = req.origin.strip()
        dest_clean = req.destination.strip()
        label = req.label or f"{origin_clean.split()[-1]} → {dest_clean.split()[-1]}"
        query = text("""
            INSERT INTO route_searches (origin, destination, label, search_count, avg_time_min, current_time_min)
            VALUES (:origin, :dest, :label, 1, 35, 38)
            ON DUPLICATE KEY UPDATE 
                search_count = search_count + 1,
                last_searched_at = CURRENT_TIMESTAMP
        """)
        db.execute(query, {
            "origin": origin_clean,
            "dest": dest_clean,
            "label": label,
        })
        db.commit()
        return {"status": "ok", "message": "경로 검색 횟수가 기록되었습니다."}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "경로 검색 기록에 실패했습니다.") from None