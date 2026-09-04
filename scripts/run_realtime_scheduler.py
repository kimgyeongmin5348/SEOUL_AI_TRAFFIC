"""RoadPulse 실시간 API 수집 스케줄러 실행 진입점."""

import sys
from pathlib import Path

# 스크립트 파일 위치가 아니라 프로젝트 루트를 import 기준으로 사용합니다.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.workers.realtime_scheduler import main


if __name__ == "__main__":
    main()
