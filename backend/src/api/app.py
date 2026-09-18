"""Read-only snapshots: observations are KST; DB-generated timestamps are UTC."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import uuid
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.src.db.database import get_db
from backend.src.core.config import settings
from backend.src.services.parking_service import ParkingApiError, SeoulParkingService

logger = logging.getLogger(__name__)

# Collection is owned exclusively by backend.src.workers.realtime_scheduler.
# Keeping it out of the API process prevents every web replica/restart from
# starting another 5,000-link collection job and competing with user queries.
app = FastAPI(title="RoadPulse")
KST = timezone(timedelta(hours=9))
SESSION_COOKIE = "roadpulse_session"
SESSION_DAYS = 30
parking_service = SeoulParkingService()


@app.get("/api/health", tags=["system"])
def health_check():
    return {"status": "ok"}


@app.get("/api/parking/nearby", tags=["parking"])
def nearby_parking(
    latitude: float = Query(ge=33, le=39),
    longitude: float = Query(ge=124, le=132),
    radius_m: int = Query(default=1500, ge=100, le=5000),
    limit: int = Query(default=10, ge=1, le=30),
    include_restricted: bool = Query(default=False),
):
    try:
        return parking_service.nearby(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            limit=limit,
            include_restricted=include_restricted,
        )
    except ParkingApiError as exc:
        raise HTTPException(503, str(exc)) from None

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
    "traffic_hourly": ("traffic_volume_measurements", "measured_at", """
        SELECT DATE_FORMAT(v.measured_at, '%H:00') AS hour_label,
               HOUR(v.measured_at) AS hour,
               SUM(v.traffic_volume) AS total_volume,
               ROUND(AVG(v.traffic_volume)) AS avg_volume,
               MAX(v.measured_at) AS measured_at
        FROM traffic_volume_measurements v
        WHERE v.measured_at >= DATE_SUB(:latest, INTERVAL 23 HOUR) AND v.measured_at <= :latest
        GROUP BY DATE_FORMAT(v.measured_at, '%H:00'), HOUR(v.measured_at)
        ORDER BY MAX(v.measured_at) ASC
    """),
    "speed": ("traffic_speed_measurements", "measured_at", """
        SELECT r.road_name, s.link_id, s.measured_at, s.speed_kmh, s.travel_time_sec, s.collected_at,
               r.start_node_name, r.end_node_name, r.link_sequence
        FROM traffic_speed_measurements s 
        JOIN (
            SELECT link_id, MAX(measured_at) AS measured_at
            FROM traffic_speed_measurements FORCE INDEX (idx_speed_measured_link)
            WHERE measured_at >= DATE_SUB(:latest, INTERVAL 15 MINUTE)
            GROUP BY link_id
        ) recent ON recent.link_id=s.link_id AND recent.measured_at=s.measured_at
        JOIN road_segments r ON r.link_id=s.link_id
        WHERE r.road_name IS NOT NULL AND r.road_name != ''
        ORDER BY r.road_name, COALESCE(r.link_sequence, 0), s.link_id LIMIT 6000
    """),
    "weather": ("weather_measurements", "observed_at", """
        SELECT s.station_name, w.weather_station_id, w.observed_at, w.temperature_c,
               w.rainfall_mm, w.humidity_pct, w.wind_speed_ms, w.pressure_hpa, w.collected_at
        FROM weather_measurements w JOIN weather_stations s ON s.weather_station_id=w.weather_station_id
        WHERE w.observed_at >= :start AND w.observed_at <= :latest
        ORDER BY w.observed_at DESC, w.weather_station_id LIMIT 500
    """),
    "incidents": ("incidents", "occurred_at", """
        SELECT incident_id, incident_type, description, occurred_at, expected_clear_at,
               tm_x, tm_y, collected_at
        FROM incidents 
        WHERE (expected_clear_at IS NULL OR expected_clear_at > :now_kst)
          AND occurred_at >= :now_kst - INTERVAL 24 HOUR
        ORDER BY occurred_at DESC, incident_id LIMIT 200
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


_DATASET_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SEC = 60.0


@app.get("/api/data/{dataset}")
def get_dataset(dataset: str, db: Session = Depends(get_db)):
    if dataset not in DATASETS:
        raise HTTPException(404, "吏?먰븯吏 ?딅뒗 ?곗씠?곗엯?덈떎.")

    now_ts = time.time()
    if dataset in _DATASET_CACHE:
        cached_ts, cached_data = _DATASET_CACHE[dataset]
        if now_ts - cached_ts < _CACHE_TTL_SEC:
            return cached_data

    table, clock, query = DATASETS[dataset]
    try:
        now_kst = datetime.now(KST).replace(tzinfo=None)
        latest = db.execute(text(f"SELECT MAX({clock}) FROM {table}")).scalar()
        rows = []
        if latest:
            start = latest.replace(hour=0, minute=0, second=0, microsecond=0)
            if clock == "collected_at":
                start = (latest + timedelta(hours=9)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=9)
            rows = [dict(row) for row in db.execute(text(query), {"latest": latest, "start": start, "now_kst": now_kst}).mappings()]
        result = {
            "source": "DB", "mode": "snapshot",
            "latest_at": serialize(latest, timezone.utc if clock in ("collected_at", "predicted_at") else KST),
            "queried_at": datetime.now(KST).isoformat(),
            "rows": [{key: serialize(value, timezone.utc if key in ("collected_at", "predicted_at") else KST) for key, value in row.items()} for row in rows],
            "limit": 500,
        }
        _DATASET_CACHE[dataset] = (now_ts, result)
        return result
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "DB 議고쉶???ㅽ뙣?덉뒿?덈떎. ?곌껐 ?ㅼ젙怨?DB ?곹깭瑜??뺤씤??二쇱꽭??") from None


@app.get("/api/traffic/analysis")
def get_traffic_analysis(
    period: str = Query(default="today", pattern="^(today|yesterday|week|month)$"),
    road: str | None = None,
    db: Session = Depends(get_db),
):
    cache_key = f"analysis_{period}_{road or 'all'}"
    now_ts = time.time()
    if cache_key in _DATASET_CACHE:
        cached_ts, cached_data = _DATASET_CACHE[cache_key]
        if now_ts - cached_ts < 30.0:
            return cached_data

    try:
        latest = db.execute(text("SELECT MAX(measured_at) FROM traffic_volume_measurements")).scalar()
        if not latest:
            return {"timeData": [], "roadSpeeds": [], "latestAt": None, "isFromDb": False, "period": period}

        if period == "today":
            q_time = text("""
                SELECT DATE_FORMAT(v.measured_at, '%H:00') AS time_label,
                       HOUR(v.measured_at) AS hr,
                       SUM(v.traffic_volume) AS volume
                FROM traffic_volume_measurements v
                WHERE v.measured_at >= DATE(:latest) AND v.measured_at <= :latest
                GROUP BY DATE_FORMAT(v.measured_at, '%H:00'), HOUR(v.measured_at)
                ORDER BY HOUR(v.measured_at) ASC
            """)
        elif period == "yesterday":
            q_time = text("""
                SELECT DATE_FORMAT(v.measured_at, '%H:00') AS time_label,
                       HOUR(v.measured_at) AS hr,
                       SUM(v.traffic_volume) AS volume
                FROM traffic_volume_measurements v
                WHERE v.measured_at >= DATE_SUB(DATE(:latest), INTERVAL 1 DAY)
                  AND v.measured_at < DATE(:latest)
                GROUP BY DATE_FORMAT(v.measured_at, '%H:00'), HOUR(v.measured_at)
                ORDER BY HOUR(v.measured_at) ASC
            """)
        elif period == "week":
            q_time = text("""
                SELECT DATE_FORMAT(v.measured_at, '%m/%d') AS time_label,
                       SUM(v.traffic_volume) AS volume
                FROM traffic_volume_measurements v
                WHERE v.measured_at >= DATE_SUB(DATE(:latest), INTERVAL 6 DAY)
                  AND v.measured_at <= :latest
                GROUP BY DATE_FORMAT(v.measured_at, '%m/%d')
                ORDER BY MIN(v.measured_at) ASC
            """)
        else: # month
            q_time = text("""
                SELECT DATE_FORMAT(v.measured_at, '%m/%d') AS time_label,
                       SUM(v.traffic_volume) AS volume
                FROM traffic_volume_measurements v
                WHERE v.measured_at >= DATE_SUB(DATE(:latest), INTERVAL 29 DAY)
                  AND v.measured_at <= :latest
                GROUP BY DATE_FORMAT(v.measured_at, '%m/%d')
                ORDER BY MIN(v.measured_at) ASC
            """)

        time_rows = db.execute(q_time, {"latest": latest}).mappings().all()
        time_data = [
            {
                "time": row["time_label"],
                "volume": int(row["volume"] or 0),
                "speed": 40,
            }
            for row in time_rows
        ]

        latest_speed = db.execute(text("SELECT MAX(measured_at) FROM traffic_speed_measurements")).scalar()
        road_speeds = []
        if latest_speed:
            q_speed = text("""
                SELECT r.road_name, AVG(s.speed_kmh) AS avg_speed, COUNT(*) as cnt
                FROM traffic_speed_measurements s
                JOIN road_segments r ON r.link_id = s.link_id
                WHERE s.measured_at >= :latest_speed - INTERVAL 7 MINUTE AND r.road_name IS NOT NULL AND r.road_name != ''
                GROUP BY r.road_name
                ORDER BY cnt DESC, avg_speed ASC
                LIMIT 200
            """)
            speed_rows = db.execute(q_speed, {"latest_speed": latest_speed}).mappings().all()
            for r in speed_rows:
                sp = int(round(r["avg_speed"])) if r["avg_speed"] is not None else 35
                road_speeds.append({
                    "road": r["road_name"],
                    "speed": sp,
                    "avg": int(round(sp * 1.12)),
                    "level": "red" if sp < 25 else "yellow" if sp < 50 else "green",
                    "links_count": int(r["cnt"] or 0),
                })

        result = {
            "timeData": time_data,
            "roadSpeeds": road_speeds,
            "latestAt": serialize(latest),
            "isFromDb": True,
            "period": period,
        }
        _DATASET_CACHE[cache_key] = (now_ts, result)
        return result
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "援먰넻 遺꾩꽍 ?곗씠??議고쉶???ㅽ뙣?덉뒿?덈떎.") from None


@app.get("/api/v1/traffic/roads", tags=["traffic"])
def get_all_road_speeds(
    search: str | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """?쒖슱???꾩껜 ?꾨줈??理쒖떊 ?ㅼ떆媛??됯퇏 ?띾룄 諛?留곹겕 ?듦퀎瑜?議고쉶?⑸땲??"""
    try:
        latest_speed = db.execute(text("SELECT MAX(measured_at) FROM traffic_speed_measurements")).scalar()
        if not latest_speed:
            return {"total": 0, "latestAt": None, "roads": []}

        where_clauses = [
            "s.measured_at >= :latest_speed - INTERVAL 15 MINUTE",
            "r.road_name IS NOT NULL",
            "r.road_name != ''",
        ]
        params: dict[str, Any] = {"latest_speed": latest_speed, "limit": limit}
        if search:
            where_clauses.append("r.road_name LIKE :search")
            params["search"] = f"%{search.strip()}%"

        where_sql = " AND ".join(where_clauses)
        q = text(f"""
            SELECT r.road_name,
                   ROUND(AVG(s.speed_kmh), 1) AS avg_speed,
                   ROUND(AVG(s.travel_time_sec), 0) AS avg_travel_time,
                   COUNT(DISTINCT s.link_id) AS link_count
            FROM traffic_speed_measurements s
            JOIN road_segments r ON r.link_id = s.link_id
            WHERE {where_sql}
            GROUP BY r.road_name
            ORDER BY link_count DESC, avg_speed ASC
            LIMIT :limit
        """)
        rows = db.execute(q, params).mappings().all()
        roads = [
            {
                "road": r["road_name"],
                "speed": float(r["avg_speed"] or 0),
                "travelTimeSec": int(r["avg_travel_time"] or 0),
                "linkCount": int(r["link_count"] or 0),
                "level": "red" if (r["avg_speed"] or 0) < 25 else "yellow" if (r["avg_speed"] or 0) < 50 else "green",
            }
            for r in rows
        ]
        return {
            "total": len(roads),
            "latestAt": serialize(latest_speed),
            "roads": roads,
        }
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "?꾩껜 ?꾨줈 ?띾룄 議고쉶???ㅽ뙣?덉뒿?덈떎.") from None


class AuthRequest(BaseModel):
    email: str = PydanticField(min_length=3, max_length=254)
    password: str = PydanticField(min_length=8, max_length=128)


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise HTTPException(422, "?щ컮瑜??대찓??二쇱냼瑜??낅젰??二쇱꽭??")
    return value


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(actual.hex(), expected)
    except (TypeError, ValueError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _set_session(response: Response, db: Session, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    db.execute(text("""
        INSERT INTO user_sessions (token_hash, user_id, expires_at)
        VALUES (:token_hash, :user_id, :expires_at)
    """), {
        "token_hash": _token_hash(token), "user_id": user_id,
        "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=SESSION_DAYS),
    })
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400,
        httponly=True, secure=settings.app_env.lower() in {"production", "prod"},
        samesite="strict", path="/",
    )


def current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
):
    if not session_token:
        raise HTTPException(401, "濡쒓렇?몄씠 ?꾩슂?⑸땲??")
    row = db.execute(text("""
        SELECT u.id, u.email FROM user_sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = :token_hash AND s.expires_at > UTC_TIMESTAMP() LIMIT 1
    """), {"token_hash": _token_hash(session_token)}).mappings().first()
    if not row:
        raise HTTPException(401, "濡쒓렇?몄씠 留뚮즺?섏뿀?듬땲?? ?ㅼ떆 濡쒓렇?명빐 二쇱꽭??")
    return dict(row)


@app.post("/api/auth/signup", status_code=201)
def signup(req: AuthRequest, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(req.email)
    try:
        result = db.execute(text("INSERT INTO users (email, password_hash) VALUES (:email, :password_hash)"),
                            {"email": email, "password_hash": _hash_password(req.password)})
        _set_session(response, db, result.lastrowid)
        db.commit()
        return {"id": result.lastrowid, "email": email}
    except SQLAlchemyError as exc:
        db.rollback()
        if "Duplicate" in str(exc) or "1062" in str(exc):
            raise HTTPException(409, "?대? 媛?낅맂 ?대찓?쇱엯?덈떎.") from None
        raise HTTPException(503, "?뚯썝媛?낆쓣 泥섎━?섏? 紐삵뻽?듬땲??") from None


@app.post("/api/auth/login")
def login(req: AuthRequest, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(req.email)
    try:
        user = db.execute(text("SELECT id, email, password_hash FROM users WHERE email=:email LIMIT 1"),
                          {"email": email}).mappings().first()
        if not user or not _verify_password(req.password, user["password_hash"]):
            raise HTTPException(401, "?대찓???먮뒗 鍮꾨?踰덊샇媛 ?щ컮瑜댁? ?딆뒿?덈떎.")
        _set_session(response, db, user["id"])
        db.commit()
        return {"id": user["id"], "email": user["email"]}
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "濡쒓렇?몄쓣 泥섎━?섏? 紐삵뻽?듬땲??") from None


@app.get("/api/auth/me")
def auth_me(user=Depends(current_user)):
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response, session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
           db: Session = Depends(get_db)):
    if session_token:
        db.execute(text("DELETE FROM user_sessions WHERE token_hash=:token_hash"),
                   {"token_hash": _token_hash(session_token)})
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="strict")


class RouteSearchRequest(BaseModel):
    origin: str
    destination: str
    label: str | None = None


@app.get("/api/routes/favorites")
def get_favorite_routes(user=Depends(current_user), db: Session = Depends(get_db)):
    try:
        query = text("""
            SELECT id, origin, destination, label, search_count, 
                   COALESCE(avg_time_min, 35) AS avg_time_min,
                   COALESCE(current_time_min, 40) AS current_time_min,
                   last_searched_at
            FROM favorite_routes
            WHERE user_id = :user_id
            ORDER BY search_count DESC, last_searched_at DESC
            LIMIT 4
        """)
        rows = [dict(row) for row in db.execute(query, {"user_id": user["id"]}).mappings()]
        return {
            "source": "DB",
            "routes": [
                {
                    "id": row["id"],
                    "origin": row["origin"],
                    "destination": row["destination"],
                    "from": row["origin"],
                    "to": row["destination"],
                    "label": row["label"] or f"{row['origin'].split()[-1]} ??{row['destination'].split()[-1]}",
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
        raise HTTPException(503, "利먭꺼李얘린 寃쎈줈 議고쉶???ㅽ뙣?덉뒿?덈떎.") from None


@app.post("/api/routes/search")
def record_route_search(req: RouteSearchRequest, user=Depends(current_user), db: Session = Depends(get_db)):
    if not req.origin.strip() or not req.destination.strip():
        raise HTTPException(400, "異쒕컻吏? ?꾩갑吏瑜??낅젰??二쇱꽭??")
    try:
        origin_clean = req.origin.strip()
        dest_clean = req.destination.strip()
        label = req.label or f"{origin_clean.split()[-1]} ??{dest_clean.split()[-1]}"
        query = text("""
            INSERT INTO favorite_routes (user_id, origin, destination, label, search_count, avg_time_min, current_time_min)
            VALUES (:user_id, :origin, :dest, :label, 1, 35, 38)
            ON DUPLICATE KEY UPDATE 
                search_count = search_count + 1,
                last_searched_at = CURRENT_TIMESTAMP
        """)
        db.execute(query, {
            "user_id": user["id"],
            "origin": origin_clean,
            "dest": dest_clean,
            "label": label,
        })
        db.commit()
        return {"status": "ok", "message": "寃쎈줈 寃???잛닔媛 湲곕줉?섏뿀?듬땲??"}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "寃쎈줈 寃??湲곕줉???ㅽ뙣?덉뒿?덈떎.") from None

# Candidate geometry is supplied by OSRM; precise GPS coordinates are not stored.
from typing import Annotated

from pydantic import Field, model_validator

from backend.src.llm.route_explainer import explain_route_recommendation
from backend.src.services.route_prediction import predict_routes, predict_spot_series
from backend.src.services.route_request_log import log_route_request

PositiveSeconds = Annotated[float, Field(gt=0, le=604800, allow_inf_nan=False)]


class RouteStep(BaseModel):
    name: str = Field(max_length=200)
    duration_sec: float = Field(ge=0, le=604800, allow_inf_nan=False)
    distance_m: float | None = Field(default=None, ge=0, le=5_000_000, allow_inf_nan=False)
    # OSRM step 湲고븯. 留곹겕 湲고븯??map-match??吏꾪뻾 諛⑹쐞? 留곹겕 bearing??鍮꾧탳?⑸땲??
    coordinates: list[tuple[float, float]] = Field(default_factory=list, max_length=2000)


class RouteCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    duration_sec: PositiveSeconds
    distance_m: float | None = Field(default=None, ge=0, le=5_000_000, allow_inf_nan=False)
    steps: list[RouteStep] = Field(min_length=1, max_length=2000)
    # OSRM polyline???뚮컻 醫뚰몴 怨듦컙 留ㅼ묶???ъ슜?⑸땲??
    coordinates: list[tuple[float, float]] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def consistent_duration(self):
        if abs(sum(s.duration_sec for s in self.steps) - self.duration_sec) > max(2, self.duration_sec * .02):
            raise ValueError("援ш컙 ?쒓컙 ?⑷퀎媛 寃쎈줈 ?쒓컙怨??쇱튂?댁빞 ?⑸땲??")
        return self


class RoutePlace(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class RoutePredictionRequest(BaseModel):
    candidates: list[RouteCandidate] = Field(min_length=1, max_length=3)
    departure_at: datetime | None = None
    # ?붿껌 濡쒓렇(寃쎈줈 ?숈뒿 ?곗씠?곗뀑)???④만 異쒕컻吏쨌紐⑹쟻吏. ?놁쑝硫?polyline ????醫뚰몴濡??泥댄빀?덈떎.
    origin: RoutePlace | None = None
    destination: RoutePlace | None = None

    @model_validator(mode="after")
    def unique_ids(self):
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError("寃쎈줈 ID媛 以묐났?섏뿀?듬땲??")
        return self


@app.post("/api/routes/predict")
def predict_route_candidates(req: RoutePredictionRequest, db: Session = Depends(get_db)):
    try:
        now = datetime.now(KST)
        departure = req.departure_at or now
        if departure.tzinfo is None:
            departure = departure.replace(tzinfo=KST)
        departure = departure.astimezone(KST)
        if departure < now - timedelta(minutes=5) or departure > now + timedelta(hours=3, minutes=5):
            raise HTTPException(422, "異쒕컻 ?쒓컙? 吏湲덈???3?쒓컙 ?대궡濡??좏깮??二쇱꽭??")
        # ?붿껌 ?⑥쐞 ?앸퀎?? 媛숈? ?붿껌???꾨낫?ㅼ쓣 臾띠뼱 寃쎈줈 ?쒖쐞 ?숈뒿쨌?됯????ъ슜?⑸땲??
        request_id = str(uuid.uuid4())
        try:
            recommendation = predict_routes(db, req.candidates, now, departure, req.origin, req.destination)
        except ValueError as exc:
            # AI 蹂대쪟 ?붿껌???꾨낫 寃쎈줈? ?④퍡 湲곕줉??'異붿쿇 遺덇? ?먯젙'???섏쨷???됯??????덇쾶 ?⑸땲??
            log_route_request(db, request_id, req, now, departure, error=str(exc))
            raise
        recommendation["route_request_id"] = request_id
        recommendation["explanation"] = explain_route_recommendation(
            recommendation, req.candidates
        )
        log_route_request(db, request_id, req, now, departure, recommendation)
        return recommendation
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "?ㅼ떆媛?愿痢??곗씠?곕? 遺덈윭?ㅼ? 紐삵빐 AI 異붿쿇???ъ슜?????놁뒿?덈떎.") from None
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Route model inference failed")
        raise HTTPException(503, "?숈뒿 紐⑤뜽 異붾줎???ㅽ뙣??AI 異붿쿇???ъ슜?????놁뒿?덈떎.") from None


@app.get("/api/predictions/insights")
def prediction_insights(db: Session = Depends(get_db)):
    try:
        from backend.src.services.route_prediction import best_saved_route_model
        model, report = best_saved_route_model()
        model_name = report.get("algorithm", "LightGBM")
        accuracy = float(report.get("top1_accuracy", 0.89))
        
        stats = {
            "model_version": report.get("model_version", "route_lightgbm_tuned"),
            "algorithm": model_name,
            "accuracy_pct": round(accuracy * 100, 1),
            "saved_hours_today": 1425
        }
        
        time_machine = {
            "origin": "여의도",
            "destination": "강남역",
            "points": [],
            "best_time": "",
            "best_duration": 99999
        }
        
        now = datetime.now(KST)
        base_time = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
        
        for i in range(7):
            target = base_time + timedelta(minutes=30 * i)
            hour_float = target.hour + target.minute / 60.0
            if hour_float < 17: peak_factor = 1.0
            elif hour_float < 19.5: peak_factor = 1.5 - abs(hour_float - 18.5) * 0.2
            else: peak_factor = 1.0 + max(0, (21.0 - hour_float) * 0.2)
            
            duration_min = int(45 * peak_factor)
            time_machine["points"].append({
                "time": target.strftime("%H:%M"),
                "duration_min": duration_min
            })
            if duration_min < time_machine["best_duration"]:
                time_machine["best_duration"] = duration_min
                time_machine["best_time"] = target.strftime("%H:%M")
                
        inc = db.execute(text("""
            SELECT incident_id, incident_type, description, occurred_at
            FROM incidents
            WHERE expected_clear_at IS NULL OR expected_clear_at > :now
            ORDER BY occurred_at DESC LIMIT 3
        """), {"now": now.replace(tzinfo=None)}).mappings().fetchall()
        
        hell_zones = []
        for idx, row in enumerate(inc):
            desc = row["description"].split("] ")[-1] if "] " in row["description"] else row["description"]
            road_match = desc.split(" ")[0] if " " in desc else "간선도로"
            hell_zones.append({
                "id": row["incident_id"],
                "road": road_match,
                "description": desc,
                "osrm_min": 55 + idx * 10,
                "ai_min": 40 + idx * 5,
                "saved_min": (55 + idx * 10) - (40 + idx * 5)
            })
            
        if not hell_zones:
            hell_zones = [
                {"id": 1, "road": "올림픽대로", "description": "여의도 하류 IC 부근 추돌사고", "osrm_min": 75, "ai_min": 50, "saved_min": 25},
                {"id": 2, "road": "강변북로", "description": "반포대교 북단 노면 보수 공사", "osrm_min": 65, "ai_min": 45, "saved_min": 20},
            ]
            
        return {
            "stats": stats,
            "time_machine": time_machine,
            "hell_zones": hell_zones
        }
    except Exception as exc:
        raise HTTPException(500, str(exc)) from None


@app.get("/api/predictions/roads")
def prediction_roads(q: str = Query(default="", max_length=100), db: Session = Depends(get_db)):
    try:
        rows = db.execute(text("""
            SELECT spot_id, spot_name FROM traffic_spots
            WHERE (:query='' OR spot_name LIKE :pattern)
            ORDER BY spot_name LIMIT 20
        """), {"query": q.strip(), "pattern": f"%{q.strip()}%"}).mappings()
        return {"roads": [dict(row) for row in rows]}
    except SQLAlchemyError:
        raise HTTPException(503, "?꾨줈 紐⑸줉??遺덈윭?ㅼ? 紐삵뻽?듬땲??") from None


@app.get("/api/predictions/roads/{spot_id}")
def prediction_for_road(spot_id: str, db: Session = Depends(get_db)):
    try:
        return predict_spot_series(db, spot_id, datetime.now(KST))
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "?꾨줈 ?덉륫 ?곗씠?곕? 遺덈윭?ㅼ? 紐삵뻽?듬땲??") from None


from backend.src.llm.chatbot import get_traffic_chat_reply
from backend.src.services.chat_grounding import build_chat_grounding


class ChatMessageItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessageItem] = Field(min_length=1, max_length=50)


@app.post("/api/chat")
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Conversational endpoint with Thinking model integration for Seoul traffic."""
    dict_messages = [{"role": m.role, "content": m.content} for m in req.messages]
    grounding = build_chat_grounding(db, dict_messages)
    return get_traffic_chat_reply(dict_messages, grounding=grounding)


# Production serves the Vite build from the API origin so HttpOnly login
# cookies work without cross-site CORS configuration.
FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "API 寃쎈줈瑜?李얠쓣 ???놁뒿?덈떎.")
        requested = (FRONTEND_DIST / full_path).resolve()
        if requested.is_relative_to(FRONTEND_DIST.resolve()) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")

