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
        # 같은 온라인 요청(라벨 있는 후보)에 대해 운영 휴리스틱·경로 모델 ETA·OSRM 기본 순서를 나란히 비교합니다.
        for basis in ("heuristic", "model_eta", "osrm"):
            print(f"[{basis}] overall: {service.evaluate(basis=basis)}")
            for grade in ("high", "medium", "low"):
                print(f"[{basis}] {grade}: {service.evaluate(grade, basis=basis)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()