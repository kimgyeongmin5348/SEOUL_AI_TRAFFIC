"""
Sync Seoul public parking lots and realtime status to the database.
- Collects master parking data from Seoul GetParkInfo API.
- Geocodes missing coordinates using Kakao Local API.
- Upserts into parking_lots.
- Collects realtime availability from GetParkingInfo API.
- Upserts into parking_realtime.
"""

import math
import sys
import time
from datetime import datetime
from typing import Any, List, Dict

import httpx
from sqlalchemy import text

from backend.src.core.config import settings
from backend.src.db.database import engine
from backend.src.services.geocoding import geocode_address

BASE_URL = "http://openapi.seoul.go.kr:8088"
PAGE_SIZE = 1000


def get_api_key() -> str:
    key = settings.seoul_parking_api_key or settings.seoul_traffic_api_key
    if not key:
        raise RuntimeError("SEOUL_PARKING_API_KEY or SEOUL_TRAFFIC_API_KEY is not configured.")
    return key


def fetch_seoul_api(service: str, client: httpx.Client) -> List[Dict[str, Any]]:
    api_key = get_api_key()
    url = f"{BASE_URL}/{api_key}/json/{service}/1/{PAGE_SIZE}/"
    res = client.get(url, timeout=30.0)
    res.raise_for_status()
    payload = res.json()
    root = payload.get(service)
    if not root:
        return []
    total = int(root.get("list_total_count") or 0)
    rows = list(root.get("row") or [])

    for start in range(PAGE_SIZE + 1, total + 1, PAGE_SIZE):
        end = min(start + PAGE_SIZE - 1, total)
        page_url = f"{BASE_URL}/{api_key}/json/{service}/{start}/{end}/"
        page_res = client.get(page_url, timeout=30.0)
        page_res.raise_for_status()
        page_root = page_res.json().get(service) or {}
        rows.extend(page_root.get("row") or [])

    return rows


def parse_restriction(name: str) -> str | None:
    if "관광버스" in name or "버스전용" in name:
        return "BUS_ONLY"
    if "화물" in name:
        return "CARGO_ONLY"
    return None


def sync_master_parking_lots() -> int:
    print("[1/2] Fetching master parking lots (GetParkInfo)...")
    with httpx.Client(timeout=30.0) as client:
        rows = fetch_seoul_api("GetParkInfo", client)
    print(f"  Fetched {len(rows)} parking records from Seoul API.")

    upsert_sql = text("""
        INSERT INTO parking_lots (
            parking_code, name, address, latitude, longitude,
            capacity, paid, restriction, operation_type, tel, coord_source, updated_at
        ) VALUES (
            :parking_code, :name, :address, :latitude, :longitude,
            :capacity, :paid, :restriction, :operation_type, :tel, :coord_source, NOW()
        )
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            address = VALUES(address),
            latitude = VALUES(latitude),
            longitude = VALUES(longitude),
            capacity = VALUES(capacity),
            paid = VALUES(paid),
            restriction = VALUES(restriction),
            operation_type = VALUES(operation_type),
            tel = VALUES(tel),
            coord_source = VALUES(coord_source),
            updated_at = NOW()
    """)

    saved_count = 0
    geocoded_count = 0
    with httpx.Client(timeout=10.0) as geo_client:
        with engine.begin() as conn:
            for idx, r in enumerate(rows):
                code = str(r.get("PKLT_CD") or "").strip()
                name = str(r.get("PKLT_NM") or "").strip()
                address = str(r.get("ADDR") or "").strip()
                if not code or not name:
                    continue

                lat = 0.0
                lon = 0.0
                try:
                    lat = float(r.get("LAT") or 0)
                    lon = float(r.get("LOT") or 0)
                except (TypeError, ValueError):
                    pass

                coord_source = "SEOUL_API"
                if not (33 <= lat <= 39 and 124 <= lon <= 132):
                    # Coordinates missing or invalid -> try geocoding
                    if address:
                        coords = geocode_address(address, geo_client)
                        if coords:
                            lat, lon = coords
                            coord_source = "GEOCODED"
                            geocoded_count += 1
                        time.sleep(0.03)

                if not (33 <= lat <= 39 and 124 <= lon <= 132):
                    # Still no valid coordinates, skip saving to avoid spatial query errors
                    continue

                capacity = int(float(r.get("TPKCT") or 0))
                paid = str(r.get("CHGD_FREE_SE") or "").upper() == "Y"
                restriction = parse_restriction(name)
                op_type = str(r.get("PRK_TYPE_NM") or r.get("OPER_SE_NM") or "")
                tel = str(r.get("TELNO") or "")

                conn.execute(upsert_sql, {
                    "parking_code": code,
                    "name": name,
                    "address": address,
                    "latitude": lat,
                    "longitude": lon,
                    "capacity": capacity,
                    "paid": paid,
                    "restriction": restriction,
                    "operation_type": op_type[:100],
                    "tel": tel[:50],
                    "coord_source": coord_source,
                })
                saved_count += 1

                if (idx + 1) % 300 == 0:
                    print(f"  Processed {idx + 1}/{len(rows)} lots... (Saved: {saved_count}, Geocoded: {geocoded_count})")

    print(f"  Master sync finished! Saved: {saved_count}, Geocoded: {geocoded_count}")
    return saved_count


def sync_realtime_parking_status() -> int:
    print("[2/2] Fetching realtime parking status (GetParkingInfo)...")
    with httpx.Client(timeout=30.0) as client:
        rows = fetch_seoul_api("GetParkingInfo", client)
    print(f"  Fetched {len(rows)} realtime records from Seoul API.")

    upsert_sql = text("""
        INSERT INTO parking_realtime (
            parking_code, capacity, occupied_spaces, available_spaces,
            realtime_status, observed_at, updated_at
        ) VALUES (
            :parking_code, :capacity, :occupied_spaces, :available_spaces,
            :realtime_status, :observed_at, NOW()
        )
        ON DUPLICATE KEY UPDATE
            capacity = VALUES(capacity),
            occupied_spaces = VALUES(occupied_spaces),
            available_spaces = VALUES(available_spaces),
            realtime_status = VALUES(realtime_status),
            observed_at = VALUES(observed_at),
            updated_at = NOW()
    """)

    saved_count = 0
    with engine.begin() as conn:
        for r in rows:
            code = str(r.get("PKLT_CD") or "").strip()
            if not code:
                continue

            capacity = int(float(r.get("TPKCT") or 0))
            occupied_raw = r.get("NOW_PRK_VHCL_CNT")
            occupied = int(float(occupied_raw)) if occupied_raw is not None else 0
            available = max(0, capacity - occupied)
            observed_at_raw = str(r.get("NOW_PRK_VHCL_UPDT_TM") or "").strip()

            observed_at = None
            if observed_at_raw:
                try:
                    observed_at = datetime.strptime(observed_at_raw, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            status = "AVAILABLE" if observed_at else "STALE"

            try:
                conn.execute(upsert_sql, {
                    "parking_code": code,
                    "capacity": capacity,
                    "occupied_spaces": occupied,
                    "available_spaces": available,
                    "realtime_status": status,
                    "observed_at": observed_at,
                })
                saved_count += 1
            except Exception:
                # If foreign key fails because parking_code is not in master, ignore
                continue

    print(f"  Realtime sync finished! Saved: {saved_count}")
    return saved_count


if __name__ == "__main__":
    t0 = time.time()
    try:
        sync_master_parking_lots()
        sync_realtime_parking_status()
        print(f"All parking data synced successfully in {time.time() - t0:.1f}s.")
    except Exception as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        sys.exit(1)
