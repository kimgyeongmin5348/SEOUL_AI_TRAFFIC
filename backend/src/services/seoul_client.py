import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from backend.src.core.config import settings

logger = logging.getLogger(__name__)


class SeoulOpenApiClient:
    BASE_URL = "http://openapi.seoul.go.kr:8088"

    def __init__(
        self,
        traffic_api_key: str | None = None,
        incident_api_key: str | None = None,
    ):
        self.traffic_api_key = traffic_api_key or settings.seoul_traffic_api_key
        self.incident_api_key = incident_api_key or settings.seoul_incident_api_key

    def _parse_xml_rows(self, xml_text: str) -> list[dict[str, str]]:
        """XML 텍스트에서 <row> 엘리먼트들을 딕셔너리 리스트로 파싱합니다."""
        rows: list[dict[str, str]] = []
        try:
            root = ET.fromstring(xml_text.strip())
            # 에러 체크
            result_code = root.findtext(".//RESULT/CODE")
            if result_code and result_code not in ("INFO-000", "INFO-200"):
                msg = root.findtext(".//RESULT/MESSAGE")
                logger.warning(f"Seoul API returned code {result_code}: {msg}")
                return []

            for row_el in root.findall(".//row"):
                row_dict: dict[str, str] = {}
                for child in row_el:
                    row_dict[child.tag.lower()] = (child.text or "").strip()
                rows.append(row_dict)
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
        return rows

    def get_traffic_spots(self, start_idx: int = 1, end_idx: int = 1000) -> list[dict[str, Any]]:
        """서울시 교통량 수집 지점 정보(SpotInfo)를 조회합니다."""
        url = f"{self.BASE_URL}/{self.traffic_api_key}/xml/SpotInfo/{start_idx}/{end_idx}/"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            raw_rows = self._parse_xml_rows(response.text)
            results = []
            for r in raw_rows:
                spot_id = r.get("spot_num")
                spot_name = r.get("spot_nm")
                tm_x_str = r.get("grs80tm_x")
                tm_y_str = r.get("grs80tm_y")
                if not spot_id or not spot_name:
                    continue
                try:
                    tm_x = float(tm_x_str) if tm_x_str else 0.0
                    tm_y = float(tm_y_str) if tm_y_str else 0.0
                except ValueError:
                    tm_x, tm_y = 0.0, 0.0

                results.append({
                    "spot_id": spot_id,
                    "spot_name": spot_name,
                    "tm_x": tm_x,
                    "tm_y": tm_y,
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch traffic spots: {e}")
            return []

    def get_link_info(self, link_id: str) -> dict[str, Any] | None:
        """도로 구간 링크 정보(LinkInfo)를 단건 조회합니다."""
        url = f"{self.BASE_URL}/{self.traffic_api_key}/xml/LinkInfo/1/5/{link_id}/"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            raw_rows = self._parse_xml_rows(response.text)
            if not raw_rows:
                return None
            r = raw_rows[0]
            length_m = None
            if r.get("map_dist"):
                try:
                    length_m = int(float(r["map_dist"]))
                except ValueError:
                    pass
            return {
                "link_id": r.get("link_id"),
                "road_name": r.get("road_name"),
                "start_node_name": r.get("st_node_nm"),
                "end_node_name": r.get("ed_node_nm"),
                "length_m": length_m,
                "region_code": r.get("reg_cd"),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch link info for {link_id}: {e}")
            return None

    def get_traffic_volume(
        self,
        spot_id: str,
        date_str: str,
        hour_str: str,
        start_idx: int = 1,
        end_idx: int = 100,
    ) -> list[dict[str, Any]]:
        """지점별 특정 일시의 교통량(VolInfo)을 조회합니다.
        date_str: YYYYMMDD
        hour_str: HH (예: '01', '14')
        """
        hh = f"{int(hour_str):02d}"
        url = f"{self.BASE_URL}/{self.traffic_api_key}/xml/VolInfo/{start_idx}/{end_idx}/{spot_id}/{date_str}/{hh}/"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            raw_rows = self._parse_xml_rows(response.text)
            results = []
            for r in raw_rows:
                # measured_at 파싱
                ymd = r.get("ymd")
                row_hh = r.get("hh", hh)
                if not ymd or not row_hh:
                    continue
                try:
                    measured_at = datetime.strptime(f"{ymd}{row_hh}", "%Y%m%d%H")
                    direction_code = int(r.get("io_type", 1))
                    lane_no = int(r.get("lane_num", 1))
                    traffic_volume = int(float(r.get("vol", 0)))
                except (ValueError, TypeError):
                    continue

                results.append({
                    "spot_id": spot_id,
                    "measured_at": measured_at,
                    "direction_code": direction_code,
                    "lane_no": lane_no,
                    "traffic_volume": traffic_volume,
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch traffic volume for {spot_id} at {date_str} {hour_str}: {e}")
            return []

    def get_traffic_speed(self, link_id: str) -> dict[str, Any] | None:
        """도로 구간 실시간 속도 및 통행시간(TrafficInfo)을 조회합니다."""
        url = f"{self.BASE_URL}/{self.traffic_api_key}/xml/TrafficInfo/1/5/{link_id}/"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            raw_rows = self._parse_xml_rows(response.text)
            if not raw_rows:
                return None
            r = raw_rows[0]
            speed_kmh = float(r.get("prcs_spd", 0.0))
            travel_time_sec = int(float(r.get("prcs_trv_time", 0)))
            return {
                "link_id": link_id,
                "measured_at": datetime.now().replace(second=0, microsecond=0),
                "speed_kmh": speed_kmh,
                "travel_time_sec": travel_time_sec,
            }
        except Exception as e:
            logger.warning(f"Failed to fetch traffic speed for {link_id}: {e}")
            return None

    def get_incidents(self, start_idx: int = 1, end_idx: int = 100) -> list[dict[str, Any]]:
        """서울시 실시간 돌발상황(AccInfo)을 조회합니다."""
        url = f"{self.BASE_URL}/{self.incident_api_key}/xml/AccInfo/{start_idx}/{end_idx}/"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            raw_rows = self._parse_xml_rows(response.text)
            results = []
            for r in raw_rows:
                incident_id = r.get("acc_id")
                if not incident_id:
                    continue

                # 발생일시 파싱
                occr_date = r.get("occr_date", "")
                occr_time = r.get("occr_time", "")
                try:
                    occurred_at = datetime.strptime(f"{occr_date}{occr_time[:4]}", "%Y%m%d%H%M")
                except ValueError:
                    occurred_at = datetime.now()

                # 종료예정일시 파싱
                exp_date = r.get("exp_clr_date", "")
                exp_time = r.get("exp_clr_time", "")
                expected_clear_at = None
                if exp_date and exp_time:
                    try:
                        expected_clear_at = datetime.strptime(f"{exp_date}{exp_time[:4]}", "%Y%m%d%H%M")
                    except ValueError:
                        pass

                tm_x = None
                if r.get("grs80tm_x"):
                    try:
                        tm_x = float(r["grs80tm_x"])
                    except ValueError:
                        pass

                tm_y = None
                if r.get("grs80tm_y"):
                    try:
                        tm_y = float(r["grs80tm_y"])
                    except ValueError:
                        pass

                results.append({
                    "incident_id": incident_id,
                    "link_id": r.get("link_id") or None,
                    "occurred_at": occurred_at,
                    "expected_clear_at": expected_clear_at,
                    "incident_type": r.get("acc_type", "UNKNOWN"),
                    "incident_detail_type": r.get("acc_dtype", "UNKNOWN"),
                    "road_code": r.get("acc_road_code"),
                    "tm_x": tm_x,
                    "tm_y": tm_y,
                    "description": r.get("acc_info"),
                })
            return results
        except Exception as e:
            logger.error(f"Failed to fetch incidents: {e}")
            return []
