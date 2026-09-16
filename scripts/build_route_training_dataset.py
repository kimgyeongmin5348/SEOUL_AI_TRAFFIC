"""서울 주요 OD 쌍의 OSRM 후보를 대량 시뮬레이션해 경로 학습 데이터셋을 생성하는 CLI.

공개 OSRM 서버(router.project-osrm.org)를 사용하므로 OD 쌍·출발 시각 수를 제한하고
호출 간 지연을 둡니다. 관측 통행시간이 있는 기간(2026-09-10~13)의 출발 시각을 기본값으로
사용해 actual_duration_sec가 실제 관측으로 채워지도록 합니다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from backend.src.db.database import SessionLocal
from backend.src.services.route_training_dataset import (
    RouteTrainingDatasetBuilder,
    write_csv,
)

# 서울 주요 출발·도착지(OD) 쌍. 좌표는 WGS84(lng, lat)입니다.
DEFAULT_OD_PAIRS = [
    ({"name": "서울역", "lat": 37.5547, "lng": 126.9707},
     {"name": "강남역", "lat": 37.4979, "lng": 127.0276}),
    ({"name": "강남역", "lat": 37.4979, "lng": 127.0276},
     {"name": "서울역", "lat": 37.5547, "lng": 126.9707}),
    ({"name": "홍대입구", "lat": 37.5572, "lng": 126.9245},
     {"name": "여의도", "lat": 37.5219, "lng": 126.9245}),
    ({"name": "잠실역", "lat": 37.5133, "lng": 127.1001},
     {"name": "광화문", "lat": 37.5716, "lng": 126.9769}),
    ({"name": "광화문", "lat": 37.5716, "lng": 126.9769},
     {"name": "잠실역", "lat": 37.5133, "lng": 127.1001}),
    ({"name": "김포공항", "lat": 37.5629, "lng": 126.8010},
     {"name": "강남역", "lat": 37.4979, "lng": 127.0276}),
    ({"name": "노원역", "lat": 37.6553, "lng": 127.0616},
     {"name": "서울역", "lat": 37.5547, "lng": 126.9707}),
    ({"name": "천호역", "lat": 37.5386, "lng": 127.1237},
     {"name": "여의도", "lat": 37.5219, "lng": 126.9245}),
    ({"name": "사당역", "lat": 37.4765, "lng": 126.9816},
     {"name": "광화문", "lat": 37.5716, "lng": 126.9769}),
    ({"name": "왕십리역", "lat": 37.5613, "lng": 127.0371},
     {"name": "목동", "lat": 37.5266, "lng": 126.8644}),
    ({"name": "수유역", "lat": 37.6381, "lng": 127.0253},
     {"name": "잠실역", "lat": 37.5133, "lng": 127.1001}),
    ({"name": "구로디지털단지", "lat": 37.4853, "lng": 126.9015},
     {"name": "강남역", "lat": 37.4979, "lng": 127.0276}),
    ({"name": "성수역", "lat": 37.5445, "lng": 127.0561},
     {"name": "김포공항", "lat": 37.5629, "lng": 126.8010}),
    ({"name": "신촌", "lat": 37.5551, "lng": 126.9368},
     {"name": "송파구청", "lat": 37.5145, "lng": 127.1059}),
    ({"name": "잠실역", "lat": 37.5133, "lng": 127.1001},
     {"name": "노원역", "lat": 37.6553, "lng": 127.0616}),
]

# 출발 시각은 기본적으로 속도 관측이 충분한 시간대를 DB에서 고릅니다. --days/--hours로 직접 줄 수도 있습니다.
MIN_OBSERVED_LINKS_PER_HOUR = 2000


def departures_from(days, hours):
    return [datetime.fromisoformat(day).replace(hour=hour) for day in days for hour in hours]


def observed_departures(db, min_links=MIN_OBSERVED_LINKS_PER_HOUR):
    """링크 관측이 min_links개 이상인 시간대(정시)만 출발 시각으로 씁니다. 관측 없는 시각은 라벨이 안 나옵니다."""
    rows = db.execute(text("""
        SELECT DATE_FORMAT(measured_at, '%Y-%m-%d %H:00:00') AS hour_bucket, COUNT(DISTINCT link_id) AS links
        FROM traffic_speed_measurements
        GROUP BY hour_bucket HAVING links >= :min_links ORDER BY hour_bucket
    """), {"min_links": min_links}).fetchall()
    return [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/processed/route_training_dataset.csv")
    parser.add_argument("--limit", type=int, default=None, help="생성할 최대 후보 행 수")
    parser.add_argument("--sleep", type=float, default=0.2, help="OSRM 호출 간 지연(초)")
    parser.add_argument("--days", nargs="*", help="출발 일자(YYYY-MM-DD). 생략하면 관측이 있는 시간대를 자동 선택")
    parser.add_argument("--hours", nargs="*", type=int, help="출발 시각(0-23). --days와 함께 사용")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        departures = departures_from(args.days, args.hours) if args.days and args.hours else observed_departures(db)
        print(f"departures: {len(departures)} ({departures[0]:%m/%d %H시} ~ {departures[-1]:%m/%d %H시})" if departures else "departures: 0")
        builder = RouteTrainingDatasetBuilder(db, sleep_sec=args.sleep)
        rows = builder.build(DEFAULT_OD_PAIRS, departures, limit=args.limit)
        output = write_csv(rows, PROJECT_ROOT / args.output)
        print(f"route training dataset: {output} ({len(rows)} rows)")
    finally:
        db.close()


if __name__ == "__main__":
    main()