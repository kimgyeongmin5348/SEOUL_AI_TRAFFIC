"""경로 후보 순위 지표(Top-1, pairwise, regret)를 계산하는 CLI."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.database import SessionLocal
from backend.src.services.route_ranking_evaluation import RouteRankingEvaluationService


def main() -> None:
    db = SessionLocal()
    try:
        service = RouteRankingEvaluationService(db)
        overall = service.evaluate()
        print(f"overall: {overall}")
        for grade in ("high", "medium", "low"):
            print(f"{grade}: {service.evaluate(grade)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()