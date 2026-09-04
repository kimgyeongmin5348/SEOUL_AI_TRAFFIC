"""모델 종류와 무관한 학습·평가·Artifact 저장 공통 로직."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import text

from backend.src.db.database import SessionLocal
from ml.src.util.config import TIME_SPLIT_RATIO


def load_time_split(dataset_path: Path, target: str = "target_volume", nrows: int | None = None):
    df = pd.read_csv(dataset_path, nrows=nrows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    excluded = {target, "datetime", "spot_id", "spot_name"}
    features = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    split_index = max(1, int(len(df) * TIME_SPLIT_RATIO))
    cutoff = df.loc[split_index, "datetime"] if split_index < len(df) else df["datetime"].max()
    train = df[df["datetime"] < cutoff]
    test = df[df["datetime"] >= cutoff]
    if train.empty or test.empty or not features:
        raise ValueError("invalid time split or no numeric features")
    return train, test, features, cutoff


def load_full_dataset(dataset_path: Path, target: str = "target_volume", nrows: int | None = None):
    """최종 학습용 전체 데이터와 숫자형 Feature를 반환합니다."""
    df = pd.read_csv(dataset_path, nrows=nrows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    excluded = {target, "datetime", "spot_id", "spot_name"}
    features = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    if df.empty or not features:
        raise ValueError("empty dataset or no numeric features")
    return df, features


def evaluate(model, test: pd.DataFrame, features: list[str], target: str) -> dict[str, float]:
    predictions = model.predict(test[features])
    return {
        "mae": float(mean_absolute_error(test[target], predictions)),
        "rmse": float(mean_squared_error(test[target], predictions) ** 0.5),
        "r2": float(r2_score(test[target], predictions)),
    }


def save_artifact(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)


def save_metrics(path: Path, metrics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


def register_model_version(*, model_version: str, algorithm: str, hyperparameters: dict[str, Any], metrics: dict[str, float], artifact_path: Path, trained_at: datetime) -> None:
    """학습 결과를 기존 model_versions 테이블에 등록합니다."""
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO model_versions (
                model_version, algorithm, hyperparameters, mae, rmse, r2_score,
                artifact_path, trained_at, is_active
            ) VALUES (
                :model_version, :algorithm, :hyperparameters, :mae, :rmse, :r2_score,
                :artifact_path, :trained_at, FALSE
            )
            ON DUPLICATE KEY UPDATE
                algorithm = VALUES(algorithm), hyperparameters = VALUES(hyperparameters),
                mae = VALUES(mae), rmse = VALUES(rmse), r2_score = VALUES(r2_score),
                artifact_path = VALUES(artifact_path), trained_at = VALUES(trained_at)
        """), {
            "model_version": model_version, "algorithm": algorithm,
            "hyperparameters": json.dumps(hyperparameters, ensure_ascii=False),
            "mae": metrics["mae"], "rmse": metrics["rmse"], "r2_score": metrics["r2"],
            "artifact_path": str(artifact_path), "trained_at": trained_at,
        })
        db.commit()
    finally:
        db.close()
