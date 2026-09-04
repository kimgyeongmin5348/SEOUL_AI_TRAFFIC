import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.db.database import engine

logger = logging.getLogger(__name__)


class DataPipelineService:
    def __init__(self, data_root: Path | None = None):
        if data_root is None:
            # 프로젝트 루트의 data 디렉터리
            self.data_root = Path(__file__).resolve().parents[3] / "data"
        else:
            self.data_root = data_root

        self.raw_dir = self.data_root / "raw"
        self.external_dir = self.data_root / "external"
        self.processed_dir = self.data_root / "processed"

        # 디렉터리가 없으면 자동 생성
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.external_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # 1단계: RDS DB에서 data/raw 및 data/external 로 원본 데이터 추출 (Export)
    # =========================================================================

    def export_raw_data(self) -> dict[str, Path]:
        """RDS MySQL 데이터베이스에서 원본 테이블들을 쿼리하여 CSV로 내보냅니다."""
        logger.info(">>> Starting DB raw data export...")
        exported_files: dict[str, Path] = {}

        with engine.connect() as conn:
            # 1. 교통량 원본 -> data/raw/raw_traffic_volume.csv
            logger.info("  [1/3] Exporting traffic_volume_measurements...")
            traffic_sql = text("""
                SELECT 
                    id, spot_id, measured_at, direction_code, lane_no, traffic_volume, collected_at
                FROM traffic_volume_measurements
                ORDER BY spot_id, measured_at, direction_code, lane_no
            """)
            df_traffic = pd.read_sql(traffic_sql, conn)
            traffic_path = self.raw_dir / "raw_traffic_volume.csv"
            df_traffic.to_csv(traffic_path, index=False, encoding="utf-8-sig")
            exported_files["traffic_volume"] = traffic_path
            logger.info(f"    Exported {len(df_traffic)} rows -> {traffic_path.name}")

            # 2. 날씨 2년치 원본 -> data/raw/raw_weather.csv
            logger.info("  [2/3] Exporting weather_measurements...")
            weather_sql = text("""
                SELECT 
                    id, weather_station_id, observed_at, temperature_c, 
                    rainfall_mm, humidity_pct, wind_speed_ms, wind_direction_deg, 
                    pressure_hpa, collected_at
                FROM weather_measurements
                ORDER BY weather_station_id, observed_at
            """)
            df_weather = pd.read_sql(weather_sql, conn)
            weather_path = self.raw_dir / "raw_weather.csv"
            df_weather.to_csv(weather_path, index=False, encoding="utf-8-sig")
            exported_files["weather"] = weather_path
            logger.info(f"    Exported {len(df_weather)} rows -> {weather_path.name}")

            # 3. 교통 지점 마스터 -> data/external/raw_traffic_spots.csv
            logger.info("  [3/3] Exporting traffic_spots metadata...")
            spots_sql = text("""
                SELECT spot_id, spot_name, tm_x, tm_y, latitude, longitude
                FROM traffic_spots
                ORDER BY spot_id
            """)
            df_spots = pd.read_sql(spots_sql, conn)
            spots_path = self.external_dir / "raw_traffic_spots.csv"
            df_spots.to_csv(spots_path, index=False, encoding="utf-8-sig")
            exported_files["traffic_spots"] = spots_path
            logger.info(f"    Exported {len(df_spots)} rows -> {spots_path.name}")

        logger.info(">>> Raw data export completed successfully.")
        return exported_files

    # =========================================================================
    # 2단계: Feature Engineering 및 최종 학습용 데이터셋 생성 (Processing)
    # =========================================================================

    def build_training_dataset(self) -> Path:
        """data/raw 와 data/external 데이터를 결합 및 정제하여 data/processed에 저장합니다."""
        traffic_path = self.raw_dir / "raw_traffic_volume.csv"
        weather_path = self.raw_dir / "raw_weather.csv"
        spots_path = self.external_dir / "raw_traffic_spots.csv"

        if not traffic_path.exists() or not weather_path.exists():
            logger.info("Raw files not found. Automatically exporting from DB first...")
            self.export_raw_data()

        logger.info(">>> Loading raw and external data for processing...")
        df_traffic = pd.read_csv(traffic_path)
        df_weather = pd.read_csv(weather_path)
        df_spots = pd.read_csv(spots_path)

        # ---------------------------------------------------------------------
        # 1. 교통량 데이터 정제 및 집계 (시간 단위, 방향별 합산)
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Aggregating traffic volume by hour & direction...")
        df_traffic["datetime"] = pd.to_datetime(df_traffic["measured_at"])
        # 분/초 제거하고 1시간 단위 정렬
        df_traffic["datetime"] = df_traffic["datetime"].dt.floor("h")

        # spot_id, datetime, direction_code 기준으로 차선(lane_no) 교통량을 합산하여 total_volume 계산
        grouped_traffic = (
            df_traffic.groupby(["spot_id", "direction_code", "datetime"], as_index=False)
            .agg({"traffic_volume": "sum"})
            .rename(columns={"traffic_volume": "target_volume"})
        )

        # ---------------------------------------------------------------------
        # 2. 날씨 데이터 정제 (시간 단위 정렬 및 결측치 보정)
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Cleaning weather measurements...")
        df_weather["datetime"] = pd.to_datetime(df_weather["observed_at"]).dt.floor("h")
        
        # 서울 대표 관측소 (108) 우선 필터링
        station_108 = df_weather[df_weather["weather_station_id"].astype(str) == "108"]
        if station_108.empty:
            station_108 = df_weather

        weather_hourly = (
            station_108.groupby("datetime", as_index=False)
            .agg({
                "temperature_c": "mean",
                "rainfall_mm": "max",
                "humidity_pct": "mean",
                "wind_speed_ms": "mean",
                "pressure_hpa": "mean",
            })
            .sort_values("datetime")
        )

        # 강수량 결측치는 0.0mm(비 안 옴)으로 대체
        weather_hourly["rainfall_mm"] = weather_hourly["rainfall_mm"].fillna(0.0)
        # 기타 기상 결측치는 시계열 보간(선형보간 후 전후값 채움)
        for col in ["temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"]:
            weather_hourly[col] = weather_hourly[col].interpolate(method="linear").bfill().ffill()

        # ---------------------------------------------------------------------
        # 3. 교통량 + 날씨 + 지점정보 조인 (Merge)
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Merging traffic volume, weather, and spots...")
        merged = pd.merge(grouped_traffic, weather_hourly, on="datetime", how="left")
        merged = pd.merge(merged, df_spots[["spot_id", "spot_name", "tm_x", "tm_y"]], on="spot_id", how="left")

        # 날씨 누락분 보정
        merged["rainfall_mm"] = merged["rainfall_mm"].fillna(0.0)
        for col in ["temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"]:
            merged[col] = merged[col].fillna(merged[col].median())

        # ---------------------------------------------------------------------
        # 4. 시간 주기성 Feature Engineering
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Generating cyclical time & calendar features...")
        dt = merged["datetime"].dt
        merged["hour"] = dt.hour
        merged["dayofweek"] = dt.dayofweek  # 0=Mon, 6=Sun
        merged["is_weekend"] = (merged["dayofweek"] >= 5).astype(int)
        merged["month"] = dt.month
        merged["day"] = dt.day

        # 출퇴근 피크 플래그 (출근: 07~09시, 퇴근: 18~20시, 주말 제외)
        is_rush_hour = merged["hour"].isin([7, 8, 9, 18, 19, 20]) & (merged["is_weekend"] == 0)
        merged["is_rush_hour"] = is_rush_hour.astype(int)

        # 24시간 및 요일 순환 주기성 인코딩 (Cyclical encoding: sin / cos)
        merged["hour_sin"] = np.sin(2 * np.pi * merged["hour"] / 24.0)
        merged["hour_cos"] = np.cos(2 * np.pi * merged["hour"] / 24.0)
        merged["day_sin"] = np.sin(2 * np.pi * merged["dayofweek"] / 7.0)
        merged["day_cos"] = np.cos(2 * np.pi * merged["dayofweek"] / 7.0)

        # ---------------------------------------------------------------------
        # 5. 시계열 지연(Lag) 및 이동통계(Rolling) Feature Engineering
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Generating lag & rolling statistical features...")
        merged = merged.sort_values(["spot_id", "direction_code", "datetime"]).reset_index(drop=True)

        grouped = merged.groupby(["spot_id", "direction_code"])

        # 1시간 전, 2시간 전, 24시간 전(전날 동시간) 교통량
        merged["vol_lag_1h"] = grouped["target_volume"].shift(1)
        merged["vol_lag_2h"] = grouped["target_volume"].shift(2)
        merged["vol_lag_24h"] = grouped["target_volume"].shift(24)

        # 최근 3시간 및 24시간 이동평균
        merged["vol_rolling_mean_3h"] = grouped["target_volume"].shift(1).rolling(3, min_periods=1).mean()
        merged["vol_rolling_mean_24h"] = grouped["target_volume"].shift(1).rolling(24, min_periods=1).mean()

        # 모델 학습을 위해 초기 Lag 결측치(최초 24시간 분량) 제거
        initial_len = len(merged)
        clean_df = merged.dropna(subset=["vol_lag_24h"]).reset_index(drop=True)
        dropped_count = initial_len - len(clean_df)
        logger.info(f"    Dropped {dropped_count} initial rows without full 24h lag history.")

        # ---------------------------------------------------------------------
        # 6. 최종 CSV 및 Feature 메타데이터 저장
        # ---------------------------------------------------------------------
        out_csv = self.processed_dir / "traffic_training_dataset.csv"
        clean_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        logger.info(f"  [Output] Saved training dataset: {out_csv} ({len(clean_df)} rows, {len(clean_df.columns)} columns)")

        meta_info = {
            "dataset_name": "seoul_ai_traffic_training_dataset",
            "generated_at": pd.Timestamp.now().isoformat(),
            "total_rows": int(len(clean_df)),
            "total_columns": int(len(clean_df.columns)),
            "target_column": "target_volume",
            "feature_columns": [c for c in clean_df.columns if c not in ["target_volume", "datetime", "spot_id", "spot_name"]],
            "all_columns": list(clean_df.columns),
            "date_range": {
                "start": str(clean_df["datetime"].min()),
                "end": str(clean_df["datetime"].max()),
            },
            "spots": list(clean_df["spot_id"].unique()),
        }

        meta_json_path = self.processed_dir / "feature_meta.json"
        with open(meta_json_path, "w", encoding="utf-8") as f:
            json.dump(meta_info, f, indent=2, ensure_ascii=False)
        logger.info(f"  [Output] Saved feature metadata: {meta_json_path}")

        return out_csv
