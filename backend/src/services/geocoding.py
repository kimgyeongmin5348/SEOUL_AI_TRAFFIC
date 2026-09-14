import os
from pathlib import Path
from typing import Tuple, Optional
import httpx

from backend.src.core.config import settings

_cached_kakao_key: Optional[str] = None


def get_kakao_key() -> Optional[str]:
    global _cached_kakao_key
    if _cached_kakao_key:
        return _cached_kakao_key

    # 1. Environment variable
    key = os.getenv("KAKAO_REST_API_KEY") or os.getenv("VITE_KAKAO_MAP_JS_KEY")
    if key:
        _cached_kakao_key = key
        return key

    # 2. Check frontend/.env.local
    frontend_env = Path("frontend/.env.local")
    if frontend_env.is_file():
        try:
            with open(frontend_env, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VITE_KAKAO_MAP_JS_KEY"):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            _cached_kakao_key = key
                            return key
        except OSError:
            pass

    return None


def geocode_address(address: str, client: Optional[httpx.Client] = None) -> Optional[Tuple[float, float]]:
    """Convert an address string into (latitude, longitude) using Kakao Local API."""
    key = get_kakao_key()
    if not key or not address or not address.strip():
        return None

    headers = {
        "Authorization": f"KakaoAK {key}",
        "KA": "os/web lang/ko-KR res/1920x1080 device/desktop app/http://localhost:5173 origin/http://localhost:5173",
        "Origin": "http://localhost:5173",
        "Referer": "http://localhost:5173/",
    }

    own_client = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        own_client = True

    try:
        # 1. Search by address
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            params={"query": address.strip()},
            headers=headers,
        )
        if res.status_code == 200:
            docs = res.json().get("documents") or []
            if docs:
                first = docs[0]
                return float(first["y"]), float(first["x"])

        # 2. Fallback to keyword search
        res = client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": address.strip(), "size": 1},
            headers=headers,
        )
        if res.status_code == 200:
            docs = res.json().get("documents") or []
            if docs:
                first = docs[0]
                return float(first["y"]), float(first["x"])

    except Exception:
        return None
    finally:
        if own_client:
            client.close()

    return None
