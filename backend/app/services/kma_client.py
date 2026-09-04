import logging
from datetime import datetime
from typing import Any

import requests

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class KmaApiClient:
    BASE_URL = "http://apis.data.go.kr/1360000/AsosHourlyInfoService"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.kma_api_key

    def get_weather_stations(self) -> list[dict[str, Any]]:
        """서울 및 수도권 주요 ASOS 관측소 기준정보를 반환합니다."""
        return [
            {
                "weather_station_id": "108",
                "station_name": "서울(송월동)",
                "latitude": 37.5714200,
                "longitude": 126.9658000,
                "elevation_m": 85.67,
                "is_active": True,
            },
            {
                "weather_station_id": "401",
                "station_name": "서울(서초)",
                "latitude": 37.4846000,
                "longitude": 127.0260000,
                "elevation_m": 42.00,
                "is_active": True,
            },
            {
                "weather_station_id": "410",
                "station_name": "서울(동작)",
                "latitude": 37.4932000,
                "longitude": 126.9171000,
                "elevation_m": 53.00,
                "is_active": True,
            },
        ]

    def get_hourly_weather(
        self,
        station_id: str = "108",
        start_date: str = "20240101",
        start_hour: str = "01",
        end_date: str = "20240101",
        end_hour: str = "23",
        num_of_rows: int = 100,
    ) -> list[dict[str, Any]]:
        """기상청 ASOS 시간자료를 조회합니다.
        start_date, end_date: YYYYMMDD
        start_hour, end_hour: HH (00~23)
        """
        url = f"{self.BASE_URL}/getWthrDataList"
        params = {
            "serviceKey": self.api_key,
            "pageNo": "1",
            "numOfRows": str(num_of_rows),
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "startDt": start_date,
            "startHh": f"{int(start_hour):02d}",
            "endDt": end_date,
            "endHh": f"{int(end_hour):02d}",
            "stnIds": station_id,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            header = data.get("response", {}).get("header", {})
            if header.get("resultCode") != "00":
                logger.warning(f"KMA API returned code {header.get('resultCode')}: {header.get('resultMsg')}")
                return []

            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            results = []
            for item in items:
                tm_str = item.get("tm")
                if not tm_str:
                    continue
                try:
                    observed_at = datetime.strptime(tm_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    continue

                def _parse_float(val: str | None) -> float | None:
                    if not val or val.strip() == "":
                        return None
                    try:
                        return float(val)
                    except ValueError:
                        return None

                def _parse_int(val: str | None) -> int | None:
                    if not val or val.strip() == "":
                        return None
                    try:
                        return int(float(val))
                    except ValueError:
                        return None

                results.append({
                    "weather_station_id": station_id,
                    "observed_at": observed_at,
                    "temperature_c": _parse_float(item.get("ta")),
                    "rainfall_mm": _parse_float(item.get("rn")),
                    "humidity_pct": _parse_float(item.get("hm")),
                    "wind_speed_ms": _parse_float(item.get("ws")),
                    "wind_direction_deg": _parse_int(item.get("wd")),
                    "pressure_hpa": _parse_float(item.get("pa")),
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch KMA weather for station {station_id}: {e}")
            return []
