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
]

# 관측 통행시간이 존재하는 기간의 출발 시각(정시).
DEFAULT_DEPARTURES = [
    datetime(2026, 9, 13, 8, 0),
    datetime(2026, 9, 13, 18, 0),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/processed/route_training_dataset.csv")
    parser.add_argument("--limit", type=int, default=None, help="생성할 최대 후보 행 수")
    parser.add_argument("--sleep", type=float, default=0.2, help="OSRM 호출 간 지연(초)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        builder = RouteTrainingDatasetBuilder(db, sleep_sec=args.sleep)
        rows = builder.build(DEFAULT_OD_PAIRS, DEFAULT_DEPARTURES, limit=args.limit)
        output = write_csv(rows, PROJECT_ROOT / args.output)
        print(f"route training dataset: {output} ({len(rows)} rows)")
    finally:
        db.close()


if __name__ == "__main__":
    main()