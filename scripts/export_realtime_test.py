"""완료된 실시간 예측을 Test CSV로 내보내는 CLI."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from backend.src.services.realtime_evaluation import RealtimeEvaluationService


def main() -> None:
    db = SessionLocal()
    try:
        service = RealtimeEvaluationService(db)
        updated = service.attach_actual_volumes()
        output = service.export_completed_test_dataset()
        print(f"actual_volume updated: {updated}")
        print(f"realtime test dataset: {output}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
