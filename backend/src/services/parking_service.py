import math
import threading
import time
from datetime import datetime
from typing import Any

import httpx

from backend.src.core.config import settings


class ParkingApiError(RuntimeError):
    """Raised when Seoul's parking API cannot provide a usable response."""


class SeoulParkingService:
    BASE_URL = "http://openapi.seoul.go.kr:8088"
    PAGE_SIZE = 1000
    MASTER_TTL_SECONDS = 6 * 60 * 60
    REALTIME_TTL_SECONDS = 5 * 60

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.seoul_parking_api_key or settings.seoul_traffic_api_key
        self._master_rows: list[dict[str, Any]] = []
        self._realtime_rows: list[dict[str, Any]] = []
        self._master_cached_at = 0.0
        self._realtime_cached_at = 0.0
        self._lock = threading.Lock()

    def _fetch_page(self, service: str, start: int, end: int) -> tuple[int, list[dict[str, Any]]]:
        if not self.api_key:
            raise ParkingApiError("서울 열린데이터광장 인증키가 설정되지 않았습니다.")

        url = f"{self.BASE_URL}/{self.api_key}/json/{service}/{start}/{end}/"
        try:
            response = httpx.get(url, timeout=20.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ParkingApiError("서울시 주차장 API 호출에 실패했습니다.") from exc

        root = payload.get(service)
        if not root:
            result = payload.get("RESULT", {})
            message = result.get("MESSAGE") or "서울시 주차장 API 응답 형식이 올바르지 않습니다."
            raise ParkingApiError(message)
        result = root.get("RESULT", {})
        if result.get("CODE") != "INFO-000":
            raise ParkingApiError(result.get("MESSAGE") or "서울시 주차장 API가 오류를 반환했습니다.")
        return int(root.get("list_total_count") or 0), list(root.get("row") or [])

    def _fetch_all(self, service: str) -> list[dict[str, Any]]:
        total, rows = self._fetch_page(service, 1, self.PAGE_SIZE)
        for start in range(self.PAGE_SIZE + 1, total + 1, self.PAGE_SIZE):
            _, page = self._fetch_page(service, start, min(start + self.PAGE_SIZE - 1, total))
            rows.extend(page)
        return rows

    def _cached_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        now = time.monotonic()
        with self._lock:
            if not self._master_rows or now - self._master_cached_at >= self.MASTER_TTL_SECONDS:
                self._master_rows = self._fetch_all("GetParkInfo")
                self._master_cached_at = now
            if not self._realtime_rows or now - self._realtime_cached_at >= self.REALTIME_TTL_SECONDS:
                self._realtime_rows = self._fetch_all("GetParkingInfo")
                self._realtime_cached_at = now
            return list(self._master_rows), list(self._realtime_rows)

    @staticmethod
    def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
        radius_m = 6_371_000
        lat_delta = math.radians(lat2 - lat1)
        lon_delta = math.radians(lon2 - lon1)
        a = (
            math.sin(lat_delta / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(lon_delta / 2) ** 2
        )
        return round(radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

    @staticmethod
    def _number(value: Any, default: int = 0) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _restriction(name: str) -> str | None:
        if "관광버스" in name or "버스전용" in name:
            return "BUS_ONLY"
        if "화물" in name:
            return "CARGO_ONLY"
        return None

    def _nearby_from_db(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int,
        include_restricted: bool,
    ) -> list[dict[str, Any]] | None:
        try:
            from sqlalchemy import text
            from backend.src.db.database import engine

            lat_delta = (radius_m + 200) / 111000.0
            cos_lat = max(0.1, math.cos(math.radians(latitude)))
            lon_delta = (radius_m + 200) / (111000.0 * cos_lat)

            query = text("""
                SELECT 
                    pl.parking_code, pl.name, pl.address, pl.latitude, pl.longitude,
                    pl.capacity, pl.paid, pl.restriction, pl.operation_type, pl.tel, pl.coord_source,
                    pr.occupied_spaces, pr.available_spaces, pr.realtime_status, pr.observed_at
                FROM parking_lots pl
                LEFT JOIN parking_realtime pr ON pl.parking_code = pr.parking_code
                WHERE pl.latitude BETWEEN :min_lat AND :max_lat
                  AND pl.longitude BETWEEN :min_lon AND :max_lon
                  AND (:include_restricted = 1 OR pl.restriction IS NULL)
            """)

            with engine.connect() as conn:
                rows = conn.execute(query, {
                    "min_lat": latitude - lat_delta,
                    "max_lat": latitude + lat_delta,
                    "min_lon": longitude - lon_delta,
                    "max_lon": longitude + lon_delta,
                    "include_restricted": 1 if include_restricted else 0,
                }).mappings().fetchall()

            if not rows:
                return None

            lots = []
            for r in rows:
                lat = float(r["latitude"])
                lon = float(r["longitude"])
                dist = self._distance_m(latitude, longitude, lat, lon)
                if dist > radius_m:
                    continue

                occupied = r["occupied_spaces"]
                capacity = int(r["capacity"] or 0)
                available = r["available_spaces"]
                realtime_status = r["realtime_status"] or "UNSUPPORTED"
                obs_at = r["observed_at"]
                obs_at_str = obs_at.isoformat() if hasattr(obs_at, "isoformat") else str(obs_at or "")

                lots.append({
                    "parking_code": r["parking_code"],
                    "name": r["name"],
                    "address": r["address"] or "",
                    "latitude": lat,
                    "longitude": lon,
                    "distance_m": dist,
                    "capacity": capacity,
                    "occupied_spaces": occupied,
                    "available_spaces": available if occupied is not None else None,
                    "realtime_status": realtime_status,
                    "observed_at": obs_at_str or None,
                    "restriction": r["restriction"],
                    "paid": bool(r["paid"]),
                })

            lots.sort(key=lambda item: item["distance_m"])
            return lots[:limit]
        except Exception:
            return None

    def nearby(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 1500,
        limit: int = 10,
        include_restricted: bool = False,
    ) -> dict[str, Any]:
        db_lots = self._nearby_from_db(latitude, longitude, radius_m, limit, include_restricted)
        if db_lots is not None:
            return {
                "source": "RoadPulse DB (Seoul + Geocoded)",
                "destination": {"latitude": latitude, "longitude": longitude},
                "radius_m": radius_m,
                "queried_at": datetime.now().astimezone().isoformat(),
                "lots": db_lots,
            }

        master_rows, realtime_rows = self._cached_rows()
        realtime_by_code = {str(row.get("PKLT_CD", "")): row for row in realtime_rows}
        nearest_by_code: dict[str, dict[str, Any]] = {}

        for row in master_rows:
            try:
                lat = float(row.get("LAT") or 0)
                lon = float(row.get("LOT") or 0)
            except (TypeError, ValueError):
                continue
            if not (33 <= lat <= 39 and 124 <= lon <= 132):
                continue

            code = str(row.get("PKLT_CD") or "")
            name = str(row.get("PKLT_NM") or "이름 없는 주차장")
            restriction = self._restriction(name)
            if not code or (restriction and not include_restricted):
                continue
            distance = self._distance_m(latitude, longitude, lat, lon)
            if distance > radius_m:
                continue

            live = realtime_by_code.get(code)
            capacity = self._number(live.get("TPKCT") if live else row.get("TPKCT"))
            occupied = self._number(live.get("NOW_PRK_VHCL_CNT")) if live else None
            observed_at = str(live.get("NOW_PRK_VHCL_UPDT_TM") or "") if live else ""
            realtime_status = "AVAILABLE" if live and observed_at else "STALE" if live else "UNSUPPORTED"
            candidate = {
                "parking_code": code,
                "name": name,
                "address": str(row.get("ADDR") or ""),
                "latitude": lat,
                "longitude": lon,
                "distance_m": distance,
                "capacity": capacity,
                "occupied_spaces": occupied,
                "available_spaces": max(0, capacity - occupied) if occupied is not None else None,
                "realtime_status": realtime_status,
                "observed_at": observed_at or None,
                "restriction": restriction,
                "paid": str((live or {}).get("PAY_YN") or row.get("CHGD_FREE_SE") or "") == "Y",
            }
            previous = nearest_by_code.get(code)
            if previous is None or distance < previous["distance_m"]:
                nearest_by_code[code] = candidate

        lots = sorted(nearest_by_code.values(), key=lambda item: item["distance_m"])[:limit]
        return {
            "source": "서울 열린데이터광장",
            "destination": {"latitude": latitude, "longitude": longitude},
            "radius_m": radius_m,
            "queried_at": datetime.now().astimezone().isoformat(),
            "lots": lots,
        }

