"""RoadPulse 실시간 수집 스케줄러.

수집 실패가 다음 주기의 작업을 막지 않도록 작업별 DB 세션을 분리합니다.
예측 작업은 모델 추론 코드가 준비된 뒤 별도 job으로 연결합니다.
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from backend.src.db.database import SessionLocal
from backend.src.services.collector_service import DataCollectorService
from backend.src.services.realtime_evaluation import RealtimeEvaluationService

logger = logging.getLogger(__name__)


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


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        lambda: run_job("fast_collection", collect_fast),
        "interval", minutes=5, id="fast_collection", max_instances=1,
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
        lambda: run_job(
            "master_sync",
            lambda collector: {
                "traffic_spots": collector.sync_traffic_spots(),
                "weather_stations": collector.sync_weather_stations(),
            },
        ),
        "interval", days=1, id="master_sync", max_instances=1,
    )
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
    )
    scheduler = build_scheduler()
    logger.info("RoadPulse realtime scheduler started")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
