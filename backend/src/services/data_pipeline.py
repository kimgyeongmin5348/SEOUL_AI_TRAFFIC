import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.src.db.database import engine

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
            logger.info("  [1/5] Exporting traffic_volume_measurements...")
            traffic_sql = text("""
                SELECT 
                    id, spot_id, measured_at, direction_code, lane_no, traffic_volume, collected_at
                FROM traffic_volume_measurements
            """)
            traffic_path = self.raw_dir / "raw_traffic_volume.csv"
            traffic_rows = 0
            first_chunk = True
            # 대용량 RDS 결과는 청크로 저장해 read timeout과 메모리 급증을 피합니다.
            for chunk in pd.read_sql(traffic_sql, conn, chunksize=100_000):
                chunk.to_csv(
                    traffic_path,
                    mode="w" if first_chunk else "a",
                    header=first_chunk,
                    index=False,
                    encoding="utf-8-sig",
                )
                traffic_rows += len(chunk)
                first_chunk = False
            exported_files["traffic_volume"] = traffic_path
            logger.info(f"    Exported {traffic_rows} rows -> {traffic_path.name}")

            # 2. 날씨 2년치 원본 -> data/raw/raw_weather.csv
            logger.info("  [2/5] Exporting weather_measurements...")
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

            # 3. 도로 링크 속도·통행시간 -> data/raw/raw_traffic_speed.csv
            logger.info("  [3/5] Exporting traffic_speed_measurements...")
            speed_sql = text("""
                SELECT link_id, measured_at, speed_kmh, travel_time_sec, collected_at
                FROM traffic_speed_measurements
            """)
            speed_path = self.raw_dir / "raw_traffic_speed.csv"
            speed_rows = 0
            first_chunk = True
            # 속도 원본도 같은 방식으로 분할 export합니다.
            for chunk in pd.read_sql(speed_sql, conn, chunksize=100_000):
                chunk.to_csv(
                    speed_path,
                    mode="w" if first_chunk else "a",
                    header=first_chunk,
                    index=False,
                    encoding="utf-8-sig",
                )
                speed_rows += len(chunk)
                first_chunk = False
            exported_files["traffic_speed"] = speed_path
            logger.info(f"    Exported {speed_rows} rows -> {speed_path.name}")

            # 4. 교통량 지점-도로 링크 매핑 -> data/external/raw_spot_road_maps.csv
            logger.info("  [4/5] Exporting traffic_spot_road_maps...")
            maps_sql = text("""
                SELECT spot_id, link_id, match_distance_m, match_method, is_primary
                FROM traffic_spot_road_maps
                ORDER BY spot_id, link_id
            """)
            df_maps = pd.read_sql(maps_sql, conn)
            maps_path = self.external_dir / "raw_spot_road_maps.csv"
            df_maps.to_csv(maps_path, index=False, encoding="utf-8-sig")
            exported_files["spot_road_maps"] = maps_path
            logger.info(f"    Exported {len(df_maps)} rows -> {maps_path.name}")

            # 5. 교통 지점 마스터 -> data/external/raw_traffic_spots.csv
            logger.info("  [5/5] Exporting traffic_spots metadata...")
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

            road_sql = text("""
                SELECT link_id, road_name, start_node_name, end_node_name, length_m, region_code
                FROM road_segments
            """)
            road_path = self.external_dir / "raw_road_segments.csv"
            pd.read_sql(road_sql, conn).to_csv(road_path, index=False, encoding="utf-8-sig")
            exported_files["road_segments"] = road_path

            incident_sql = text("""
                SELECT incident_id, link_id, occurred_at, expected_clear_at,
                       incident_type, incident_detail_type, description
                FROM incidents
            """)
            incident_path = self.raw_dir / "raw_incidents.csv"
            pd.read_sql(incident_sql, conn).to_csv(incident_path, index=False, encoding="utf-8-sig")
            exported_files["incidents"] = incident_path

        logger.info(">>> Raw data export completed successfully.")
        return exported_files

    # =========================================================================
    # 2단계: Feature Engineering 및 최종 학습용 데이터셋 생성 (Processing)
    # =========================================================================

    def build_training_dataset(self) -> Path:
        """data/raw 와 data/external 데이터를 결합 및 정제하여 data/processed에 저장합니다."""
        traffic_path = self.raw_dir / "raw_traffic_volume.csv"
        speed_path = self.raw_dir / "raw_traffic_speed.csv"
        weather_path = self.raw_dir / "raw_weather.csv"
        spots_path = self.external_dir / "raw_traffic_spots.csv"
        maps_path = self.external_dir / "raw_spot_road_maps.csv"

        if not all(path.exists() for path in (traffic_path, speed_path, weather_path, spots_path, maps_path)):
            logger.info("Raw files not found. Automatically exporting from DB first...")
            self.export_raw_data()

        logger.info(">>> Loading raw and external data for processing...")
        df_traffic = pd.read_csv(traffic_path)
        df_speed = pd.read_csv(speed_path)
        df_weather = pd.read_csv(weather_path)
        df_spots = pd.read_csv(spots_path)
        df_maps = pd.read_csv(maps_path)

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
        # 1-1. 속도·통행시간을 측정지점 단위 및 서울시 전역 단위로 집계 (미래 정보 방지)
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Aggregating linked speed and Seoul-wide network speed...")
        df_speed["datetime"] = pd.to_datetime(df_speed["measured_at"]).dt.floor("h")
        df_speed_hourly = (
            df_speed.groupby(["link_id", "datetime"], as_index=False)
            .agg(speed_kmh=("speed_kmh", "mean"), travel_time_sec=("travel_time_sec", "mean"))
        )

        # 서울시 전체 도로 링크(5,200개 링크)의 시간별 거시 평균 속도 및 소통 통계
        df_seoul_speed_hourly = (
            df_speed.groupby("datetime", as_index=False)
            .agg(
                seoul_avg_speed=("speed_kmh", "mean"),
                seoul_avg_travel_time=("travel_time_sec", "mean"),
            )
            .sort_values("datetime")
        )
        df_seoul_speed_hourly["seoul_avg_speed_lag_1h"] = df_seoul_speed_hourly["seoul_avg_speed"].shift(1)
        df_seoul_speed_hourly["seoul_avg_travel_time_lag_1h"] = df_seoul_speed_hourly["seoul_avg_travel_time"].shift(1)
        seoul_speed_features = df_seoul_speed_hourly[["datetime", "seoul_avg_speed_lag_1h", "seoul_avg_travel_time_lag_1h"]]

        df_maps = df_maps[df_maps["is_primary"].astype(bool)]
        speed_by_spot = df_maps[["spot_id", "link_id"]].merge(
            df_speed_hourly, on="link_id", how="inner"
        )
        speed_by_spot = (
            speed_by_spot.groupby(["spot_id", "datetime"], as_index=False)
            .agg(speed_kmh=("speed_kmh", "mean"), travel_time_sec=("travel_time_sec", "mean"))
            .sort_values(["spot_id", "datetime"])
        )
        # The target at t may not use the speed observed during t.
        speed_by_spot["speed_lag_1h"] = speed_by_spot.groupby("spot_id")["speed_kmh"].shift(1)
        speed_by_spot["travel_time_lag_1h"] = speed_by_spot.groupby("spot_id")["travel_time_sec"].shift(1)
        speed_by_spot["speed_data_available"] = speed_by_spot["speed_lag_1h"].notna().astype(int)
        speed_features = speed_by_spot[[
            "spot_id", "datetime", "speed_lag_1h", "travel_time_lag_1h", "speed_data_available",
        ]]

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
        weather_hourly["weather_source_datetime"] = weather_hourly["datetime"]

        # 강수량 결측치는 0.0mm(비 안 옴)으로 대체
        weather_hourly["rainfall_mm"] = weather_hourly["rainfall_mm"].fillna(0.0)
        # 온라인 추론과 같은 조건을 유지하기 위해 과거 관측값만 사용합니다.
        for col in ["temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"]:
            weather_hourly[col] = weather_hourly[col].ffill()
        weather_hourly["weather_source_datetime"] = weather_hourly["weather_source_datetime"].ffill()

        # ---------------------------------------------------------------------
        # 3. 교통량 + 날씨 + 서울시 전역 속도 + 지점정보 조인 (Merge)
        # ---------------------------------------------------------------------
        logger.info("  [Processing] Merging traffic volume, weather, Seoul speed, and spots...")
        merged = pd.merge(grouped_traffic, weather_hourly, on="datetime", how="left")
        merged = pd.merge(merged, seoul_speed_features, on="datetime", how="left")
        merged = pd.merge(merged, speed_features, on=["spot_id", "datetime"], how="left")
        merged = pd.merge(merged, df_spots[["spot_id", "spot_name", "tm_x", "tm_y"]], on="spot_id", how="left")

        # 서울시 전역 평균 속도 결측 보정
        if "seoul_avg_speed_lag_1h" in merged.columns:
            merged["seoul_avg_speed_lag_1h"] = merged["seoul_avg_speed_lag_1h"].ffill().bfill().fillna(35.0)
            merged["seoul_avg_travel_time_lag_1h"] = merged["seoul_avg_travel_time_lag_1h"].ffill().bfill().fillna(60.0)

        # 관측 이전 구간은 미래값으로 채우지 않고 학습에서 제외합니다.
        merged["weather_observed"] = (
            merged["weather_source_datetime"] == merged["datetime"]
        ).astype(int)
        merged["weather_age_hours"] = (
            (merged["datetime"] - merged["weather_source_datetime"]).dt.total_seconds() / 3600
        )
        merged = merged.dropna(subset=[
            "temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa",
        ]).reset_index(drop=True)

        # 강수량만 결측을 0으로 해석합니다. 다른 결측은 위에서 제거했습니다.
        merged["rainfall_mm"] = merged["rainfall_mm"].fillna(0.0)

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
            "feature_columns": [
                c for c in clean_df.columns
                if c not in ["target_volume", "datetime", "spot_id", "spot_name"]
                and pd.api.types.is_numeric_dtype(clean_df[c])
            ],
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

    def build_link_training_dataset(self) -> Path:
        """Build a link-level speed/travel-time dataset without future features."""
        required = [
            self.raw_dir / "raw_traffic_speed.csv",
            self.raw_dir / "raw_weather.csv",
            self.raw_dir / "raw_incidents.csv",
            self.external_dir / "raw_road_segments.csv",
        ]
        if not all(path.exists() for path in required):
            self.export_raw_data()

        speed = pd.read_csv(required[0])
        weather = pd.read_csv(required[1])
        incidents = pd.read_csv(required[2])
        roads = pd.read_csv(required[3])
        speed["datetime"] = pd.to_datetime(speed["measured_at"]).dt.floor("h")
        speed = speed.groupby(["link_id", "datetime"], as_index=False).agg(
            speed_kmh=("speed_kmh", "mean"), travel_time_sec=("travel_time_sec", "mean")
        )
        speed = speed.merge(roads, on="link_id", how="left")
        speed = speed.sort_values(["link_id", "datetime"])
        grouped = speed.groupby("link_id", sort=False)
        speed["speed_lag_1h"] = grouped["speed_kmh"].shift(1)
        speed["travel_time_lag_1h"] = grouped["travel_time_sec"].shift(1)
        speed["target_speed_kmh"] = grouped["speed_kmh"].shift(-1)
        speed["target_travel_time_sec"] = grouped["travel_time_sec"].shift(-1)
        speed["target_datetime"] = grouped["datetime"].shift(-1)
        # 다음 관측이 정확히 한 시간 뒤일 때만 학습 정답으로 사용합니다.
        speed["consecutive_next_hour"] = (
            speed["target_datetime"] - speed["datetime"] == pd.Timedelta(hours=1)
        ).astype(int)

        weather["datetime"] = pd.to_datetime(weather["observed_at"]).dt.floor("h")
        weather = weather[weather["weather_station_id"].astype(str) == "108"]
        weather = weather.groupby("datetime", as_index=False).agg(
            temperature_c=("temperature_c", "mean"), rainfall_mm=("rainfall_mm", "max"),
            humidity_pct=("humidity_pct", "mean"), wind_speed_ms=("wind_speed_ms", "mean"),
            pressure_hpa=("pressure_hpa", "mean"),
        ).sort_values("datetime")
        weather["rainfall_mm"] = weather["rainfall_mm"].fillna(0.0)
        for column in ["temperature_c", "humidity_pct", "wind_speed_ms", "pressure_hpa"]:
            weather[column] = weather[column].ffill()
        # 미래 기상값을 과거 링크 행에 역전파하지 않습니다.
        weather["weather_source_datetime"] = weather["datetime"]
        weather["weather_source_datetime"] = weather["weather_source_datetime"].ffill()
        speed = speed.merge(weather, on="datetime", how="left")
        speed["weather_available"] = speed["temperature_c"].notna().astype(int)
        speed["weather_age_hours"] = (
            (speed["datetime"] - speed["weather_source_datetime"]).dt.total_seconds() / 3600
        )

        incidents["occurred_at"] = pd.to_datetime(incidents["occurred_at"])
        incidents["expected_clear_at"] = pd.to_datetime(incidents["expected_clear_at"])
        incident_rows = []
        # 발생·해제 시각이 링크 관측 시각과 겹치는 돌발만 feature로 집계합니다.
        for link_id, group in incidents.groupby("link_id", dropna=True):
            for _, row in group.iterrows():
                active = speed[(speed["link_id"] == link_id) & (speed["datetime"] >= row["occurred_at"])]
                if pd.notna(row["expected_clear_at"]):
                    active = active[active["datetime"] <= row["expected_clear_at"]]
                if not active.empty:
                    incident_rows.append(pd.DataFrame({
                        "link_id": link_id, "datetime": active["datetime"],
                        "active_incident_count": 1,
                        "accident_count": int(row["incident_type"] == "A01"),
                        "construction_count": int(row["incident_type"] == "A04"),
                        "control_count": int(row["incident_type"] in {"A08", "A10"}),
                        "breakdown_count": int(row["incident_type"] == "A02"),
                    }))
        if incident_rows:
            incident_features = pd.concat(incident_rows).groupby(["link_id", "datetime"], as_index=False).sum()
            speed = speed.merge(incident_features, on=["link_id", "datetime"], how="left")
        for column in ["active_incident_count", "accident_count", "construction_count", "control_count", "breakdown_count"]:
            if column not in speed:
                speed[column] = 0
            else:
                speed[column] = speed[column].fillna(0).astype(int)

        output = self.processed_dir / "link_training_dataset.csv"
        speed = speed[
            (speed["consecutive_next_hour"] == 1)
            & (speed["weather_available"] == 1)
        ].dropna(subset=["speed_lag_1h", "target_speed_kmh"])
        speed.to_csv(output, index=False, encoding="utf-8-sig")
        metadata = {
            "dataset_name": "seoul_ai_traffic_link_training_dataset",
            "generated_at": pd.Timestamp.now().isoformat(),
            "total_rows": int(len(speed)),
            "total_columns": int(len(speed.columns)),
            "entity_key": "link_id",
            "targets": ["target_speed_kmh", "target_travel_time_sec"],
            "feature_columns": [
                column for column in speed.columns
                if column not in {"target_speed_kmh", "target_travel_time_sec", "target_datetime"}
                and column not in {"link_id", "datetime", "road_name", "start_node_name", "end_node_name"}
                and pd.api.types.is_numeric_dtype(speed[column])
            ],
            "date_range": {
                "start": str(speed["datetime"].min()),
                "end": str(speed["datetime"].max()),
            },
            "links": int(speed["link_id"].nunique()),
            "incident_rows": int((speed["active_incident_count"] > 0).sum()),
        }
        (self.processed_dir / "link_feature_meta.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[Output] Saved link training dataset: %s (%s rows, %s columns)", output, len(speed), len(speed.columns))
        return output
