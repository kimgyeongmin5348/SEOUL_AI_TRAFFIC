import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트 경로를 sys.path에 추가
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from backend.src.services.data_pipeline import DataPipelineService

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ProcessDataCLI")


def print_dataset_summary(csv_path: Path):
    """생성된 최종 학습용 데이터셋의 요약 정보를 출력합니다."""
    df = pd.read_csv(csv_path)
    print("\n" + "=" * 60)
    print(f"📁 학습용 데이터셋 생성 완료: {csv_path.name}")
    print("=" * 60)
    print(f"  • 총 데이터 건수 (Rows)   : {len(df):,} 행")
    print(f"  • 총 특성 컬럼 수 (Cols)  : {len(df.columns)} 개")
    print(f"  • 수집 기간 (Date Range)  : {df['datetime'].min()} ~ {df['datetime'].max()}")
    print(f"  • 대상 지점 (Spots)       : {list(df['spot_id'].unique())}")
    print("-" * 60)
    print("📋 주요 특성 컬럼 목록:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_count = df[col].isnull().sum()
        print(f"    - {col:<24} : {dtype:<10} (결측치: {null_count})")
    print("=" * 60 + "\n")

    print("🔎 데이터 샘플 (상위 3개 행):")
    cols_to_preview = [
        "datetime", "spot_id", "direction_code", "target_volume",
        "vol_lag_1h", "vol_lag_24h", "temperature_c", "rainfall_mm", "is_rush_hour"
    ]
    avail_cols = [c for c in cols_to_preview if c in df.columns]
    print(df[avail_cols].head(3).to_string(index=False))
    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="RoadPulse DB 데이터 추출 및 AI 학습용 전처리 데이터셋 생성 스크립트"
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="DB에서 data/raw 및 data/external 로 추출만 수행합니다.",
    )
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="기존에 추출된 data/raw 파일들을 바탕으로 data/processed 생성만 수행합니다.",
    )

    args = parser.parse_args()
    pipeline = DataPipelineService()

    try:
        if args.export_only:
            print("\n>>> [Step 1] DB -> data/raw, data/external 추출 시작...\n")
            exported = pipeline.export_raw_data()
            print("\n>>> DB 데이터 추출 완료!")
            for name, path in exported.items():
                print(f"  • {name:<20} -> {path}")
        elif args.process_only:
            print("\n>>> [Step 2] data/raw -> data/processed 전처리 시작...\n")
            out_path = pipeline.build_training_dataset()
            print_dataset_summary(out_path)
        else:
            # 기본 동작: 1단계 추출 -> 2단계 전처리 일괄 수행
            print("\n>>> [전체 파이프라인] DB 추출 -> 전처리 -> 학습 데이터셋 생성 시작...\n")
            pipeline.export_raw_data()
            out_path = pipeline.build_training_dataset()
            print_dataset_summary(out_path)

    except Exception as e:
        logger.error(f"Error during data pipeline execution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
