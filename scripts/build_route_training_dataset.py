"""서울 주요 OD 쌍의 OSRM 후보를 대량 시뮬레이션해 경로 학습 데이터셋을 생성하는 CLI.

공개 OSRM 서버(router.project-osrm.org)를 사용하므로 OD 쌍·출발 시각 수를 제한하고
호출 간 지연을 둡니다. 관측 통행시간이 있는 기간(2026-09-10~13)의 출발 시각을 기본값으로
사용해 actual_duration_sec가 실제 관측으로 채워지도록 합니다.
"""

import argparse
import json
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
_POINTS = [
    {"name": "서울역", "lat": 37.5547, "lng": 126.9707},
    {"name": "강남역", "lat": 37.4979, "lng": 127.0276},
    {"name": "홍대입구", "lat": 37.5572, "lng": 126.9245},
    {"name": "여의도", "lat": 37.5219, "lng": 126.9245},
    {"name": "잠실역", "lat": 37.5133, "lng": 127.1001},
    {"name": "광화문", "lat": 37.5716, "lng": 126.9769},
    {"name": "김포공항", "lat": 37.5629, "lng": 126.8010},
    {"name": "노원역", "lat": 37.6553, "lng": 127.0616},
    {"name": "천호역", "lat": 37.5386, "lng": 127.1237},
    {"name": "사당역", "lat": 37.4765, "lng": 126.9816},
    {"name": "왕십리역", "lat": 37.5613, "lng": 127.0371},
    {"name": "목동", "lat": 37.5266, "lng": 126.8644},
    {"name": "수유역", "lat": 37.6381, "lng": 127.0253},
    {"name": "구로디지털단지", "lat": 37.4853, "lng": 126.9015},
    {"name": "성수역", "lat": 37.5445, "lng": 127.0561},
    {"name": "신촌", "lat": 37.5551, "lng": 126.9368},
    {"name": "송파구청", "lat": 37.5145, "lng": 127.1059},
    {"name": "은평구청", "lat": 37.6027, "lng": 126.9291},
    {"name": "강동구청", "lat": 37.5301, "lng": 127.1238},
    {"name": "동대문", "lat": 37.5714, "lng": 127.0094},
    {"name": "청량리역", "lat": 37.5800, "lng": 127.0470},
    {"name": "양재역", "lat": 37.4842, "lng": 127.0344},
    {"name": "신림역", "lat": 37.4842, "lng": 126.9295},
    {"name": "미아사거리", "lat": 37.6134, "lng": 127.0300},
    {"name": "합정역", "lat": 37.5496, "lng": 126.9139},
    {"name": "건대입구", "lat": 37.5404, "lng": 127.0693},
    {"name": "서울대입구", "lat": 37.4812, "lng": 126.9527},
    {"name": "상암DMC", "lat": 37.5776, "lng": 126.8912},
]

import random
random.seed(42)
DEFAULT_OD_PAIRS = []
while len(DEFAULT_OD_PAIRS) < 150:
    o, d = random.sample(_POINTS, 2)
    if (o, d) not in DEFAULT_OD_PAIRS:
        DEFAULT_OD_PAIRS.append((o, d))

# 출발 시각은 기본적으로 속도 관측이 충분한 시간대를 DB에서 고릅니다. --days/--hours로 직접 줄 수도 있습니다.
MIN_OBSERVED_LINKS_PER_HOUR = 2000


def departures_from(days, hours):
    return [datetime.fromisoformat(day).replace(hour=hour) for day in days for hour in hours]


def observed_departures(db, min_links=MIN_OBSERVED_LINKS_PER_HOUR):
    """링크 관측이 min_links개 이상인 시간대(정시)만 출발 시각으로 씁니다. 관측 없는 시각은 라벨이 안 나옵니다."""
    rows = db.execute(text("""
        SELECT DATE_FORMAT(measured_at, '%Y-%m-%d %H:00:00') AS hour_bucket, COUNT(DISTINCT link_id) AS links
        FROM traffic_speed_measurements
        WHERE measured_at >= DATE_SUB(NOW(), INTERVAL 14 DAY)
        GROUP BY hour_bucket HAVING links >= :min_links ORDER BY hour_bucket
    """), {"min_links": min_links}).fetchall()
    return [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in rows]


# 컬럼 역할. 검사 스크립트(check_route_dataset.py)와 학습기가 이 정의를 기준으로 삼습니다.
IDENTITY_COLUMNS = ["route_request_id", "route_id", "departure_at", "origin_name", "origin_lat", "origin_lng",
                    "destination_name", "destination_lat", "destination_lng"]
FEATURE_COLUMNS = [
    "departure_hour", "weekday", "is_weekend",
    "route_distance_m", "osrm_duration_sec", "segment_count",
    "link_match_ratio", "direction_match_ratio", "opposite_direction_ratio",
    "speed_lag_kmh", "speed_lag_min_kmh", "speed_lag_travel_time_sec", "speed_lag_coverage", "speed_lag_age_min",
    "speed_data_available",
    "volume_lag_vph_mean", "volume_lag_vph_max", "volume_lag_coverage", "volume_lag_age_hours",
    "accident_count", "construction_count", "control_count", "breakdown_count", "active_incident_count",
    "control_length_m", "blocked_length_m", "incident_severity_max", "incident_impact_score",
    "incident_clear_overlap_sec", "incident_match_ratio", "incident_data_age_sec",
    "weather_temperature_c", "weather_rainfall_mm", "weather_humidity_pct", "weather_age_hours",
]
# 피처가 참조한 관측 시각. 모두 departure_at 이전이어야 합니다(누수 검사 대상).
FEATURE_TIMESTAMP_COLUMNS = ["speed_lag_observed_at", "volume_lag_observed_at", "weather_observed_at"]
LABEL_COLUMNS = ["actual_duration_sec", "actual_delay_sec", "route_rank_actual", "chosen_best"]
QUALITY_COLUMNS = ["actual_duration_quality", "observed_length_ratio", "label_observed_at_min", "label_observed_at_max"]


def dataset_metadata(rows, departures):
    labelled = [r for r in rows if r["actual_duration_sec"] is not None]
    quality = {}
    for row in rows:
        quality[row["actual_duration_quality"]] = quality.get(row["actual_duration_quality"], 0) + 1
    return {
        "dataset": "route_training_dataset.csv",
        "unit": "한 행 = 한 후보 경로 × 한 출발 시각. 같은 route_request_id의 후보끼리 순위를 비교한다.",
        "label": {
            "actual_duration_sec": "step에 배분된 링크 길이 × 주행 중간 시각(출발+OSRM/2) ±60분 관측 속도로 재구성한 통행시간(초). "
                                    "관측 없는 길이는 OSRM 시간을 길이 비례로 유지. 관측 설명 길이 비율 0.3 미만이면 NULL(unusable).",
            "actual_delay_sec": "actual_duration_sec - osrm_duration_sec",
            "route_rank_actual": "같은 요청 안 라벨 있는 후보의 통행시간 순위(1=최적). 라벨 있는 후보 2개 미만이면 NULL",
            "chosen_best": "route_rank_actual == 1",
        },
        "leakage_rule": "피처는 출발 시각 이전에 수집된 값만 사용(속도·교통량은 measured_at/collected_at ≤ departure, 돌발은 collected_at ≤ departure, "
                        "기상은 observed_at ≤ departure). 라벨은 주행 시간대 관측만 사용. *_observed_at 컬럼으로 검사한다.",
        "known_limits": [
            "라벨은 실제 주행 기록이 아니라 링크 관측 속도 재구성값이다.",
            "교통량 lag는 측정지점(139개)→링크 매핑이 방향을 구분하지 않아 지점 양방향 합계이며 커버리지가 낮다.",
            "OSRM 후보는 데이터셋 생성 시점의 도로망·자유속도 기준이고 출발 시각별로 다시 조회하지 않는다.",
        ],
        "identity_columns": IDENTITY_COLUMNS,
        "feature_columns": FEATURE_COLUMNS,
        "feature_timestamp_columns": FEATURE_TIMESTAMP_COLUMNS,
        "label_columns": LABEL_COLUMNS,
        "quality_columns": QUALITY_COLUMNS,
        "od_pairs": len(DEFAULT_OD_PAIRS),
        "departures": len(departures),
        "departure_range": [departures[0].isoformat(), departures[-1].isoformat()] if departures else None,
        "rows": len(rows),
        "requests": len({r["route_request_id"] for r in rows}),
        "labelled_rows": len(labelled),
        "quality_counts": quality,
    }


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
        meta_path = output.with_name("route_feature_meta.json")
        meta_path.write_text(json.dumps(dataset_metadata(rows, departures), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"metadata: {meta_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()