"""실시간 예측 결과에 실제 교통량을 연결하고 평가용 CSV를 생성합니다."""

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


class RealtimeEvaluationService:
    def __init__(self, db: Session, output_dir: Path | None = None):
        self.db = db
        self.output_dir = output_dir or Path(__file__).resolve().parents[3] / "data" / "online"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def attach_actual_volumes(self) -> int:
        """예측 대상 시간이 지난 행에 시간·방향별 실제 차로 합계를 연결합니다."""
        result = self.db.execute(text("""
            UPDATE traffic_predictions p
            JOIN (
                SELECT spot_id, direction_code, measured_at,
                       SUM(traffic_volume) AS actual_volume
                FROM traffic_volume_measurements
                GROUP BY spot_id, direction_code, measured_at
            ) v ON v.spot_id = p.spot_id
               AND v.direction_code = p.direction_code
               AND v.measured_at = p.target_at
            SET p.actual_volume = v.actual_volume
            WHERE p.actual_volume IS NULL
              AND p.target_at <= CURRENT_TIMESTAMP
        """))
        self.db.commit()
        return result.rowcount

    def export_completed_test_dataset(self) -> Path:
        """완료된 예측만 DB에서 재생성하여 온라인 Test CSV로 내보냅니다."""
        df = pd.read_sql(text("""
            SELECT
                p.id, p.spot_id, p.direction_code, p.model_version,
                p.predicted_at, p.target_at, p.predicted_volume,
                p.actual_volume,
                ABS(p.predicted_volume - p.actual_volume) AS absolute_error,
                (p.predicted_volume - p.actual_volume) AS error
            FROM traffic_predictions p
            WHERE p.actual_volume IS NOT NULL
            ORDER BY p.target_at, p.spot_id, p.direction_code, p.model_version
        """), self.db.bind)
        output = self.output_dir / "realtime_test_dataset.csv"
        df.to_csv(output, index=False, encoding="utf-8-sig")
        return output
