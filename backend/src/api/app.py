"""Read-only snapshots: observations are KST; DB-generated timestamps are UTC."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import os
import re
import secrets

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.src.db.database import get_db
from backend.src.core.config import settings

app = FastAPI(title="RoadPulse")
KST = timezone(timedelta(hours=9))
SESSION_COOKIE = "roadpulse_session"
SESSION_DAYS = 30

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

from pydantic import BaseModel, Field as PydanticField


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
from backend.src.services.route_prediction import predict_routes

PositiveSeconds = Annotated[float, Field(gt=0, le=604800, allow_inf_nan=False)]


class RouteStep(BaseModel):
    name: str = Field(max_length=200)
    duration_sec: float = Field(ge=0, le=604800, allow_inf_nan=False)


class RouteCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    duration_sec: PositiveSeconds
    steps: list[RouteStep] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def consistent_duration(self):
        if abs(sum(s.duration_sec for s in self.steps) - self.duration_sec) > max(2, self.duration_sec * .02):
            raise ValueError("구간 시간 합계가 경로 시간과 일치해야 합니다.")
        return self


class RoutePredictionRequest(BaseModel):
    candidates: list[RouteCandidate] = Field(min_length=1, max_length=3)
    departure_at: datetime | None = None

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
        return predict_routes(db, req.candidates, now, departure)
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
