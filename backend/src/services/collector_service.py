import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.src.services.kma_client import KmaApiClient
from backend.src.services.seoul_client import SeoulOpenApiClient

logger = logging.getLogger(__name__)


class DataCollectorService:
    def __init__(
        self,
        db: Session,
        seoul_client: SeoulOpenApiClient | None = None,
        kma_client: KmaApiClient | None = None,
    ):
        self.db = db
        self.seoul_client = seoul_client or SeoulOpenApiClient()
        self.kma_client = kma_client or KmaApiClient()

    # =========================================================================
    # 1단계: 기준정보 (Master Data) 적재
    # =========================================================================

    def sync_traffic_spots(self) -> int:
        """서울시 교통량 수집 지점(SpotInfo)을 조회하여 traffic_spots 테이블에 적재합니다."""
        spots = self.seoul_client.get_traffic_spots(start_idx=1, end_idx=1000)
        if not spots:
            logger.warning("No traffic spots retrieved from API.")
            return 0

        sql = text("""
            INSERT INTO traffic_spots (spot_id, spot_name, tm_x, tm_y)
            VALUES (:spot_id, :spot_name, :tm_x, :tm_y)
            ON DUPLICATE KEY UPDATE
                spot_name = VALUES(spot_name),
                tm_x = VALUES(tm_x),
                tm_y = VALUES(tm_y),
                updated_at = CURRENT_TIMESTAMP
        """)

        for spot in spots:
            self.db.execute(sql, spot)
        self.db.commit()
        logger.info(f"Successfully synced {len(spots)} traffic spots.")
        return len(spots)

    def sync_weather_stations(self) -> int:
        """기상청 주요 ASOS 관측소 기준정보를 weather_stations 테이블에 적재합니다."""
        stations = self.kma_client.get_weather_stations()
        sql = text("""
            INSERT INTO weather_stations (
                weather_station_id, station_name, latitude, longitude, elevation_m, is_active
            )
            VALUES (
                :weather_station_id, :station_name, :latitude, :longitude, :elevation_m, :is_active
            )
            ON DUPLICATE KEY UPDATE
                station_name = VALUES(station_name),
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                elevation_m = VALUES(elevation_m),
                is_active = VALUES(is_active)
        """)
        for st in stations:
            self.db.execute(sql, st)
        self.db.commit()
        logger.info(f"Successfully synced {len(stations)} weather stations.")
        return len(stations)

    def ensure_road_segment(self, link_id: str) -> bool:
        """주어진 link_id가 road_segments에 존재하는지 확인하고 없으면 API를 통해 가져와 적재합니다."""
        check_sql = text("SELECT 1 FROM road_segments WHERE link_id = :link_id")
        exists = self.db.execute(check_sql, {"link_id": link_id}).scalar()
        if exists:
            return True

        # API로 도로 구간 정보 조회
        link_info = self.seoul_client.get_link_info(link_id)
        if not link_info or not link_info.get("link_id"):
            # API에 정보가 없으면 기본값으로 레코드 생성 (FK 무결성 보장)
            link_info = {
                "link_id": link_id,
                "road_name": f"링크_{link_id}",
                "start_node_name": None,
                "end_node_name": None,
                "length_m": None,
                "region_code": None,
            }

        insert_sql = text("""
            INSERT INTO road_segments (
                link_id, road_name, start_node_name, end_node_name, length_m, region_code
            )
            VALUES (
                :link_id, :road_name, :start_node_name, :end_node_name, :length_m, :region_code
            )
            ON DUPLICATE KEY UPDATE
                road_name = COALESCE(VALUES(road_name), road_name),
                start_node_name = COALESCE(VALUES(start_node_name), start_node_name),
                end_node_name = COALESCE(VALUES(end_node_name), end_node_name),
                length_m = COALESCE(VALUES(length_m), length_m),
                region_code = COALESCE(VALUES(region_code), region_code),
                updated_at = CURRENT_TIMESTAMP
        """)
        self.db.execute(insert_sql, link_info)
        self.db.commit()
        return True

    # =========================================================================
    # 2단계: 측정값 (Measurements) 및 실시간 데이터 적재
    # =========================================================================

    def sync_traffic_volume(
        self,
        spot_ids: list[str] | None = None,
        date_str: str | None = None,
        hours: list[str] | None = None,
    ) -> int:
        """지점별 교통량(VolInfo)을 수집하여 traffic_volume_measurements 테이블에 적재합니다."""
        # 지점 목록이 없으면 DB에서 상위 지점들을 조회
        if not spot_ids:
            # 실시간 운영에서는 139개 전체 지점을 대상으로 수집합니다.
            query = text("SELECT spot_id FROM traffic_spots ORDER BY spot_id")
            rows = self.db.execute(query).fetchall()
            spot_ids = [r[0] for r in rows]

        if not spot_ids:
            logger.warning("No spot_ids available for traffic volume sync.")
            return 0

        # 기본값: API에서 확정된 최신 시간대(약 2시간 전)를 1시간 수집
        if not date_str:
            latest_hour = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
            date_str = latest_hour.strftime("%Y%m%d")
            default_hour = latest_hour.strftime("%H")
        else:
            default_hour = None

        # 과거 호출에서 hours를 명시하면 해당 범위를 유지하고,
        # 실시간 호출에서는 확정된 최신 1시간만 조회합니다.
        if not hours:
            hours = [default_hour or "00"]

        sql = text("""
            INSERT INTO traffic_volume_measurements (
                spot_id, measured_at, direction_code, lane_no, traffic_volume
            )
            VALUES (
                :spot_id, :measured_at, :direction_code, :lane_no, :traffic_volume
            )
            ON DUPLICATE KEY UPDATE
                traffic_volume = VALUES(traffic_volume),
                collected_at = CURRENT_TIMESTAMP
        """)

        total_inserted = 0
        for spot_id in spot_ids:
            for hh in hours:
                records = self.seoul_client.get_traffic_volume(
                    spot_id=spot_id,
                    date_str=date_str,
                    hour_str=hh,
                )
                for rec in records:
                    self.db.execute(sql, rec)
                    total_inserted += 1

        self.db.commit()
        logger.info(f"Successfully synced {total_inserted} traffic volume measurements.")
        return total_inserted

    def sync_traffic_speed(self, link_ids: list[str] | None = None) -> int:
        """도로 구간 링크별 실시간 속도(TrafficInfo)를 수집하여 traffic_speed_measurements 테이블에 적재합니다."""
        if not link_ids:
            # 기본 주요 간선도로 링크 목록
            link_ids = [
                "1220003800",  # 분당수서로
                "1000000100",  # 세종대로
                "1210000500",  # 강남대로
                "1220001100",  # 올림픽대로
                "1230016700",  # 송파대로
            ]

        # FK 보장을 위해 link_id가 road_segments에 존재하는지 먼저 보장
        for link_id in link_ids:
            self.ensure_road_segment(link_id)

        sql = text("""
            INSERT INTO traffic_speed_measurements (
                link_id, measured_at, speed_kmh, travel_time_sec
            )
            VALUES (
                :link_id, :measured_at, :speed_kmh, :travel_time_sec
            )
            ON DUPLICATE KEY UPDATE
                speed_kmh = VALUES(speed_kmh),
                travel_time_sec = VALUES(travel_time_sec),
                collected_at = CURRENT_TIMESTAMP
        """)

        total_inserted = 0
        for link_id in link_ids:
            speed_data = self.seoul_client.get_traffic_speed(link_id)
            if speed_data:
                self.db.execute(sql, speed_data)
                total_inserted += 1

        self.db.commit()
        logger.info(f"Successfully synced {total_inserted} traffic speed measurements.")
        return total_inserted

    def sync_weather_measurements(
        self,
        station_id: str = "108",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        """기상청 ASOS 시간자료를 수집하여 weather_measurements 테이블에 적재합니다."""
        # 관측소 마스터 존재 보장
        self.sync_weather_stations()

        if not start_date or not end_date:
            # ASOS는 시간 관측자료이므로 오늘 누적분 중 최신 관측 시각까지 조회합니다.
            now = datetime.now()
            start_date = now.strftime("%Y%m%d")
            end_date = start_date
            end_hour = max(now.hour - 1, 0)
        else:
            end_hour = 23

        records = self.kma_client.get_hourly_weather(
            station_id=station_id,
            start_date=start_date,
            start_hour="00",
            end_date=end_date,
            end_hour=f"{end_hour:02d}",
        )
        if not records:
            logger.warning(f"No weather records retrieved for station {station_id}.")
            return 0

        sql = text("""
            INSERT INTO weather_measurements (
                weather_station_id, observed_at, temperature_c, rainfall_mm,
                humidity_pct, wind_speed_ms, wind_direction_deg, pressure_hpa
            )
            VALUES (
                :weather_station_id, :observed_at, :temperature_c, :rainfall_mm,
                :humidity_pct, :wind_speed_ms, :wind_direction_deg, :pressure_hpa
            )
            ON DUPLICATE KEY UPDATE
                temperature_c = VALUES(temperature_c),
                rainfall_mm = VALUES(rainfall_mm),
                humidity_pct = VALUES(humidity_pct),
                wind_speed_ms = VALUES(wind_speed_ms),
                wind_direction_deg = VALUES(wind_direction_deg),
                pressure_hpa = VALUES(pressure_hpa),
                collected_at = CURRENT_TIMESTAMP
        """)

        for rec in records:
            self.db.execute(sql, rec)
        self.db.commit()
        logger.info(f"Successfully synced {len(records)} weather measurements.")
        return len(records)

    def sync_incidents(self) -> int:
        """서울시 실시간 돌발상황(AccInfo)을 수집하여 incidents 테이블에 적재합니다."""
        incidents = self.seoul_client.get_incidents(start_idx=1, end_idx=100)
        if not incidents:
            logger.warning("No incidents retrieved from API.")
            return 0

        # FK 보장: 각 incident의 link_id가 존재하면 road_segments에 등록
        for inc in incidents:
            link_id = inc.get("link_id")
            if link_id:
                self.ensure_road_segment(link_id)

        sql = text("""
            INSERT INTO incidents (
                incident_id, link_id, occurred_at, expected_clear_at,
                incident_type, incident_detail_type, road_code,
                tm_x, tm_y, description
            )
            VALUES (
                :incident_id, :link_id, :occurred_at, :expected_clear_at,
                :incident_type, :incident_detail_type, :road_code,
                :tm_x, :tm_y, :description
            )
            ON DUPLICATE KEY UPDATE
                link_id = VALUES(link_id),
                expected_clear_at = VALUES(expected_clear_at),
                incident_type = VALUES(incident_type),
                incident_detail_type = VALUES(incident_detail_type),
                road_code = VALUES(road_code),
                tm_x = VALUES(tm_x),
                tm_y = VALUES(tm_y),
                description = VALUES(description),
                collected_at = CURRENT_TIMESTAMP
        """)

        for inc in incidents:
            self.db.execute(sql, inc)
        self.db.commit()
        logger.info(f"Successfully synced {len(incidents)} incidents.")
        return len(incidents)

    # =========================================================================
    # 대량 이력 데이터 (Historical Training Dataset) 수집 메서드
    # =========================================================================

    def sync_weather_history(
        self,
        station_id: str = "108",
        start_year: int = 2024,
        end_year: int = 2025,
    ) -> int:
        """지정 기간(기본: 2024년~2025년, 2년 치)의 기상청 시간자료를 월별로 일괄 수집/적재합니다."""
        import calendar

        self.sync_weather_stations()
        total_synced = 0

        sql = text("""
            INSERT INTO weather_measurements (
                weather_station_id, observed_at, temperature_c, rainfall_mm,
                humidity_pct, wind_speed_ms, wind_direction_deg, pressure_hpa
            )
            VALUES (
                :weather_station_id, :observed_at, :temperature_c, :rainfall_mm,
                :humidity_pct, :wind_speed_ms, :wind_direction_deg, :pressure_hpa
            )
            ON DUPLICATE KEY UPDATE
                temperature_c = VALUES(temperature_c),
                rainfall_mm = VALUES(rainfall_mm),
                humidity_pct = VALUES(humidity_pct),
                wind_speed_ms = VALUES(wind_speed_ms),
                wind_direction_deg = VALUES(wind_direction_deg),
                pressure_hpa = VALUES(pressure_hpa),
                collected_at = CURRENT_TIMESTAMP
        """)

        logger.info(f"Starting KMA weather history sync ({start_year} ~ {end_year}) for station {station_id}...")

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                _, last_day = calendar.monthrange(year, month)
                start_date = f"{year}{month:02d}01"
                end_date = f"{year}{month:02d}{last_day:02d}"

                records = self.kma_client.get_hourly_weather(
                    station_id=station_id,
                    start_date=start_date,
                    start_hour="01",
                    end_date=end_date,
                    end_hour="23",
                    num_of_rows=800,
                )

                if records:
                    for rec in records:
                        self.db.execute(sql, rec)
                    self.db.commit()
                    total_synced += len(records)
                    logger.info(f"  [Weather {year}-{month:02d}] Synced {len(records)} hours (Total: {total_synced})")

        logger.info(f"Finished KMA weather history sync. Total: {total_synced} rows.")
        return total_synced

    def sync_traffic_volume_history(
        self,
        spot_ids: list[str] | None = None,
        days: int = 30,
        end_date: datetime | None = None,
    ) -> int:
        """핵심 지점에 대해 최근 N일간의 24시간 연속 교통량 데이터를 수집/적재합니다."""
        import time

        self.sync_traffic_spots()

        if not spot_ids:
            spot_ids = ["C-02"]  # 대표 지점

        if not end_date:
            end_date = datetime.now() - timedelta(days=1)

        sql = text("""
            INSERT INTO traffic_volume_measurements (
                spot_id, measured_at, direction_code, lane_no, traffic_volume
            )
            VALUES (
                :spot_id, :measured_at, :direction_code, :lane_no, :traffic_volume
            )
            ON DUPLICATE KEY UPDATE
                traffic_volume = VALUES(traffic_volume),
                collected_at = CURRENT_TIMESTAMP
        """)

        total_synced = 0
        date_list = [(end_date - timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
        hours = [f"{h:02d}" for h in range(1, 25)]  # 01시 ~ 24시

        logger.info(
            f"Starting traffic volume history sync: spots={spot_ids}, days={days} ({date_list[-1]} ~ {date_list[0]})..."
        )

        for spot_id in spot_ids:
            for d_idx, d_str in enumerate(date_list, 1):
                day_records_count = 0
                for hh in hours:
                    records = self.seoul_client.get_traffic_volume(
                        spot_id=spot_id,
                        date_str=d_str,
                        hour_str=hh,
                    )
                    for rec in records:
                        self.db.execute(sql, rec)
                        total_synced += 1
                        day_records_count += 1
                    time.sleep(0.02)  # 짧은 간격으로 안전 호출

                self.db.commit()
                logger.info(
                    f"  [Spot {spot_id} - Day {d_idx}/{days} ({d_str})] Synced {day_records_count} records (Total: {total_synced})"
                )

        logger.info(f"Finished traffic volume history sync. Total: {total_synced} rows.")
        return total_synced

    def sync_all(self) -> dict[str, int]:
        """모든 기준정보와 측정값을 올바른 의존성 순서에 따라 일괄 수집/적재합니다."""
        summary: dict[str, int] = {}
        logger.info("=== 1단계: 기준정보(Master Data) 동기화 시작 ===")
        summary["traffic_spots"] = self.sync_traffic_spots()
        summary["weather_stations"] = self.sync_weather_stations()

        logger.info("=== 2단계: 실시간 및 이력 측정값 동기화 시작 ===")
        summary["traffic_volume"] = self.sync_traffic_volume()
        summary["traffic_speed"] = self.sync_traffic_speed()
        summary["weather_measurements"] = self.sync_weather_measurements()
        summary["incidents"] = self.sync_incidents()

        logger.info(f"=== 동기화 완료 요약: {summary} ===")
        return summary
