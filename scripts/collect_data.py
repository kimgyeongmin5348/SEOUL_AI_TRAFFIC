import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import text

from backend.src.db.database import SessionLocal, engine
from backend.src.services.collector_service import DataCollectorService

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("CollectDataCLI")
# 서울 OpenAPI 인증키는 URL 경로에 포함되므로 HTTP 요청 URL 로깅을 끕니다.
logging.getLogger("httpx").setLevel(logging.WARNING)


if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def print_table_status():
    """현재 DB의 주요 테이블 레코드 수를 출력합니다."""
    tables = [
        "traffic_spots",
        "road_segments",
        "weather_stations",
        "traffic_volume_measurements",
        "traffic_speed_measurements",
        "weather_measurements",
        "incidents",
    ]
    print("\n" + "=" * 50)
    print("[STATUS] RDS Database Row Count Summary")
    print("=" * 50)
    with engine.connect() as conn:
        for t in tables:
            try:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                print(f"  * {t:<30} : {cnt:>6} rows")
            except Exception as e:
                print(f"  * {t:<30} : Query Failed ({e})")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="RoadPulse Data Ingestion Script for Seoul Public Data & KMA APIs"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 기준정보 및 측정값을 일괄 수집/적재합니다.",
    )
    parser.add_argument(
        "--master",
        action="store_true",
        help="교통 지점 및 기상 관측소 기준정보만 수집합니다.",
    )
    parser.add_argument(
        "--traffic",
        action="store_true",
        help="교통량(VolInfo) 및 속도(TrafficInfo)를 수집합니다.",
    )
    parser.add_argument(
        "--weather",
        action="store_true",
        help="기상청 ASOS 시간 관측값을 수집합니다.",
    )
    parser.add_argument(
        "--incidents",
        action="store_true",
        help="서울시 실시간 돌발정보(AccInfo)를 수집합니다.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="기상청 2년치(2024~2025) 날씨와 대표 지점 30일치 연속 교통량을 일괄 수집합니다.",
    )
    parser.add_argument(
        "--weather-history",
        action="store_true",
        help="기상청 2년치(2024~2025) 시간별 날씨 데이터를 전수 수집합니다.",
    )
    parser.add_argument(
        "--traffic-history",
        action="store_true",
        help="대표 지점의 최근 N일간 24시간 연속 교통량을 수집합니다.",
    )
    parser.add_argument(
        "--backfill-hours",
        type=int,
        metavar="N",
        help="전체 교통량 지점의 최근 N시간을 실제 API 데이터로 백필합니다.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="--traffic-history 수집 일수 (기본값: 30일)",
    )
    parser.add_argument(
        "--spot",
        type=str,
        default="C-02",
        help="--traffic-history 수집 대상 지점 ID (기본값: C-02)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="현재 데이터베이스 적재 현황만 조회합니다.",
    )

    args = parser.parse_args()

    # 인자가 아무것도 없으면 --status 출력
    if not any([
        args.all, args.master, args.traffic, args.weather,
        args.incidents, args.history, args.weather_history,
        args.traffic_history, args.backfill_hours, args.status
    ]):
        args.status = True

    if args.status:
        print_table_status()
        return

    db = SessionLocal()
    collector = DataCollectorService(db=db)

    try:
        print("\n>>> Starting Data Collection & DB Ingestion Pipeline...\n")
        if args.history:
            collector.sync_weather_history(start_year=2024, end_year=2025)
            collector.sync_traffic_volume_history(spot_ids=[args.spot], days=args.days)
        elif args.weather_history:
            collector.sync_weather_history(start_year=2024, end_year=2025)
        elif args.traffic_history:
            collector.sync_traffic_volume_history(spot_ids=[args.spot], days=args.days)
        elif args.backfill_hours:
            if args.backfill_hours < 1 or args.backfill_hours > 72:
                parser.error("--backfill-hours는 1~72 사이여야 합니다.")
            # VolInfo is finalized about two hours late. Group requests by date
            # because its endpoint accepts one date and one or more hours.
            end = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
            by_date: dict[str, list[str]] = defaultdict(list)
            for offset in range(args.backfill_hours):
                point = end - timedelta(hours=offset)
                by_date[point.strftime("%Y%m%d")].append(point.strftime("%H"))
            total = 0
            collector.sync_traffic_spots()
            for date_str, hours in sorted(by_date.items()):
                total += collector.sync_traffic_volume(
                    date_str=date_str,
                    hours=sorted(hours),
                )
            logger.info("최근 %s시간 교통량 백필 완료: %s행", args.backfill_hours, total)
        elif args.all:
            collector.sync_all()
        else:
            if args.master:
                collector.sync_traffic_spots()
                collector.sync_weather_stations()
            if args.traffic:
                collector.sync_traffic_spots()  # FK 보장
                collector.sync_traffic_volume()
                collector.sync_traffic_speed()
            if args.weather:
                collector.sync_weather_measurements()
            if args.incidents:
                collector.sync_incidents()

        print("\n>>> Data Collection & DB Ingestion Complete!\n")
        print_table_status()


    except Exception as e:
        logger.error(f"Error during data collection: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()



if __name__ == "__main__":
    main()
