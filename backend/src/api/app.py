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
        raise HTTPException(404, "지원하지 않는 데이터입니다.")

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
        raise HTTPException(503, "DB 조회에 실패했습니다. 연결 설정과 DB 상태를 확인해 주세요.") from None


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
        raise HTTPException(503, "교통 분석 데이터 조회에 실패했습니다.") from None


@app.get("/api/v1/traffic/roads", tags=["traffic"])
def get_all_road_speeds(
    search: str | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """서울시 전체 도로의 최신 실시간 평균 속도 및 링크 통계를 조회합니다."""
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
        raise HTTPException(503, "전체 도로 속도 조회에 실패했습니다.") from None


class AuthRequest(BaseModel):
    email: str = PydanticField(min_length=3, max_length=254)
    password: str = PydanticField(min_length=8, max_length=128)


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise HTTPException(422, "올바른 이메일 주소를 입력해 주세요.")
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
        raise HTTPException(401, "로그인이 필요합니다.")
    row = db.execute(text("""
        SELECT u.id, u.email FROM user_sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = :token_hash AND s.expires_at > UTC_TIMESTAMP() LIMIT 1
    """), {"token_hash": _token_hash(session_token)}).mappings().first()
    if not row:
        raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인해 주세요.")
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
            raise HTTPException(409, "이미 가입된 이메일입니다.") from None
        raise HTTPException(503, "회원가입을 처리하지 못했습니다.") from None


@app.post("/api/auth/login")
def login(req: AuthRequest, response: Response, db: Session = Depends(get_db)):
    email = _normalize_email(req.email)
    try:
        user = db.execute(text("SELECT id, email, password_hash FROM users WHERE email=:email LIMIT 1"),
                          {"email": email}).mappings().first()
        if not user or not _verify_password(req.password, user["password_hash"]):
            raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다.")
        _set_session(response, db, user["id"])
        db.commit()
        return {"id": user["id"], "email": user["email"]}
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "로그인을 처리하지 못했습니다.") from None


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
def record_route_search(req: RouteSearchRequest, user=Depends(current_user), db: Session = Depends(get_db)):
    if not req.origin.strip() or not req.destination.strip():
        raise HTTPException(400, "출발지와 도착지를 입력해 주세요.")
    try:
        origin_clean = req.origin.strip()
        dest_clean = req.destination.strip()
        label = req.label or f"{origin_clean.split()[-1]} → {dest_clean.split()[-1]}"
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
        return {"status": "ok", "message": "경로 검색 횟수가 기록되었습니다."}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "경로 검색 기록에 실패했습니다.") from None

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
    # OSRM step 기하. 링크 기하에 map-match해 진행 방위와 링크 bearing을 비교합니다.
    coordinates: list[tuple[float, float]] = Field(default_factory=list, max_length=2000)


class RouteCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    duration_sec: PositiveSeconds
    distance_m: float | None = Field(default=None, ge=0, le=5_000_000, allow_inf_nan=False)
    steps: list[RouteStep] = Field(min_length=1, max_length=2000)
    # OSRM polyline을 돌발 좌표 공간 매칭에 사용합니다.
    coordinates: list[tuple[float, float]] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def consistent_duration(self):
        if abs(sum(s.duration_sec for s in self.steps) - self.duration_sec) > max(2, self.duration_sec * .02):
            raise ValueError("구간 시간 합계가 경로 시간과 일치해야 합니다.")
        return self


class RoutePlace(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class RoutePredictionRequest(BaseModel):
    candidates: list[RouteCandidate] = Field(min_length=1, max_length=3)
    departure_at: datetime | None = None
    # 요청 로그(경로 학습 데이터셋)에 남길 출발지·목적지. 없으면 polyline 양 끝 좌표로 대체합니다.
    origin: RoutePlace | None = None
    destination: RoutePlace | None = None

    @model_validator(mode="after")
    def unique_ids(self):
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError("경로 ID가 중복되었습니다.")
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
            raise HTTPException(422, "출발 시간은 지금부터 3시간 이내로 선택해 주세요.")
        # 요청 단위 식별자: 같은 요청의 후보들을 묶어 경로 순위 학습·평가에 사용합니다.
        request_id = str(uuid.uuid4())
        try:
            recommendation = predict_routes(db, req.candidates, now, departure)
        except ValueError as exc:
            # AI 보류 요청도 후보 경로와 함께 기록해 '추천 불가 판정'을 나중에 평가할 수 있게 합니다.
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
        raise HTTPException(503, "실시간 관측 데이터를 불러오지 못해 AI 추천을 사용할 수 없습니다.") from None
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Route model inference failed")
        raise HTTPException(503, "학습 모델 추론에 실패해 AI 추천을 사용할 수 없습니다.") from None


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
        raise HTTPException(503, "도로 목록을 불러오지 못했습니다.") from None


@app.get("/api/predictions/roads/{spot_id}")
def prediction_for_road(spot_id: str, db: Session = Depends(get_db)):
    try:
        return predict_spot_series(db, spot_id, datetime.now(KST))
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "도로 예측 데이터를 불러오지 못했습니다.") from None


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
            raise HTTPException(404, "API 경로를 찾을 수 없습니다.")
        requested = (FRONTEND_DIST / full_path).resolve()
        if requested.is_relative_to(FRONTEND_DIST.resolve()) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
