"""실시간 스케줄러 job 구성 검증."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from apscheduler.schedulers.background import BackgroundScheduler

from backend.src.workers import realtime_scheduler
from backend.src.workers.realtime_scheduler import KST, ROUTE_LABEL_DELAY, build_scheduler, reconstruct_route_labels


def test_scheduler_registers_route_label_job_and_runs_master_sync_at_start():
    scheduler = build_scheduler(BackgroundScheduler, run_immediately=True)
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert "route_label_reconstruction" in jobs
    assert jobs["route_label_reconstruction"].trigger.interval == timedelta(hours=1)
    # 기준정보 동기화(축·방향 컬럼)는 프로세스 시작 직후 한 번 실행됩니다.
    assert jobs["master_sync"].next_run_time is not None
    assert jobs["route_label_reconstruction"].next_run_time is not None


def test_reconstruct_route_labels_only_labels_trips_that_finished():
    collector = MagicMock()
    with patch.object(realtime_scheduler, "RouteDurationReconstructionService") as service:
        service.return_value.reconstruct.return_value = 3
        result = reconstruct_route_labels(collector)
    assert result == {"route_candidates_labelled": 3}
    cutoff = service.return_value.reconstruct.call_args.kwargs["now"]
    # KST naive 기준으로 출발 후 90분이 지난 요청만 대상입니다.
    assert cutoff.tzinfo is None
    expected = datetime.now(KST).replace(tzinfo=None) - ROUTE_LABEL_DELAY
    assert abs(expected - cutoff) < timedelta(minutes=1)
