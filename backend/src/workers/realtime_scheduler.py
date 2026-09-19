"""RoadPulse 실시간 수집 스케줄러.

수집 실패가 다음 주기의 작업을 막지 않도록 작업별 DB 세션을 분리합니다.
예측 작업은 모델 추론 코드가 준비된 뒤 별도 job으로 연결합니다.
"""

import logging

from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.base import BaseScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from backend.src.db.database import SessionLocal
from backend.src.services.collector_service import DataCollectorService
from backend.src.services.realtime_evaluation import RealtimeEvaluationService
from backend.src.services.route_duration_reconstruction import RouteDurationReconstructionService

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
# 출발 후 이 시간이 지난 요청만 라벨을 만듭니다. 주행 시간대 관측이 모두 들어온 뒤에 재구성해야
# 출발 전 관측만으로 라벨이 만들어지는 것을 막을 수 있습니다.
ROUTE_LABEL_DELAY = timedelta(minutes=90)


def run_job(job_name: str, callback) -> None:
    db = SessionLocal()
    try:
        result = callback(DataCollectorService(db=db))
        logger.info("%s completed: %s", job_name, result)
    except Exception:
        logger.exception("%s failed", job_name)
    finally:
        db.close()


def collect_fast(collector: DataCollectorService) -> dict[str, int]:
    return {
        "traffic_speed": collector.sync_traffic_speed(),
        "incidents": collector.sync_incidents(),
    }


def collect_hourly(collector: DataCollectorService) -> dict[str, int]:
    return {
        "traffic_volume": collector.sync_traffic_volume(),
        "weather_measurements": collector.sync_weather_measurements(),
    }


def evaluate_completed_predictions(collector: DataCollectorService) -> dict[str, object]:
    evaluation = RealtimeEvaluationService(collector.db)
    updated = evaluation.attach_actual_volumes()
    output = evaluation.export_completed_test_dataset()
    return {"actuals_attached": updated, "test_dataset": str(output)}


def reconstruct_route_labels(collector: DataCollectorService) -> dict[str, int]:
    """경로 요청 로그의 후보에 링크 관측 기반 actual_duration_sec를 채웁니다 (경로 학습 라벨)."""
    # route_requests.departure_at은 KST naive이고 서버 시계는 UTC일 수 있으므로 KST로 비교합니다.
    cutoff = datetime.now(KST).replace(tzinfo=None) - ROUTE_LABEL_DELAY
    updated = RouteDurationReconstructionService(collector.db).reconstruct(now=cutoff)
    return {"route_candidates_labelled": updated}


def build_scheduler(
    scheduler_cls: type[BaseScheduler] = BlockingScheduler,
    run_immediately: bool = True,
) -> BaseScheduler:
    scheduler = scheduler_cls(timezone="Asia/Seoul")
    fast_next_run = datetime.now() if run_immediately else None
    scheduler.add_job(
        lambda: run_job("fast_collection", collect_fast),
        "interval", minutes=1, id="fast_collection", max_instances=1,
        next_run_time=fast_next_run,
    )
    scheduler.add_job(
        lambda: run_job("hourly_collection", collect_hourly),
        "interval", hours=1, id="hourly_collection", max_instances=1,
    )
    scheduler.add_job(
        lambda: run_job("prediction_evaluation", evaluate_completed_predictions),
        "interval", hours=1, id="prediction_evaluation", max_instances=1,
    )
    scheduler.add_job(
        lambda: run_job("route_label_reconstruction", reconstruct_route_labels),
        "interval", hours=1, id="route_label_reconstruction", max_instances=1,
        next_run_time=fast_next_run,
    )
    scheduler.add_job(
        lambda: run_job(
            "master_sync",
            lambda collector: {
                "traffic_spots": collector.sync_traffic_spots(),
                "road_segments": collector.sync_road_segments(),
                "weather_stations": collector.sync_weather_stations(),
            },
        ),
        # 기준정보(축·방향 포함)는 시작 직후 한 번 맞추고 이후 하루에 한 번 갱신합니다.
        "interval", days=1, id="master_sync", max_instances=1,
        next_run_time=fast_next_run,
    )
    return scheduler


def start_background_scheduler() -> BackgroundScheduler:
    scheduler = build_scheduler(scheduler_cls=BackgroundScheduler, run_immediately=True)
    scheduler.start()
    logger.info("RoadPulse background scheduler started in-process")
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
    )
    # Seoul OpenAPI keys are embedded in URL paths; never print request URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    scheduler = build_scheduler(BlockingScheduler, run_immediately=True)
    logger.info("RoadPulse realtime scheduler started")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
