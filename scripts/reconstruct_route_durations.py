"""경로 요청 로그에 링크 관측 기반 actual_duration_sec를 채우는 CLI."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from backend.src.services.route_duration_reconstruction import RouteDurationReconstructionService


def main() -> None:
    db = SessionLocal()
    try:
        service = RouteDurationReconstructionService(db)
        updated = service.reconstruct()
        print(f"actual_duration_sec reconstructed: {updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()