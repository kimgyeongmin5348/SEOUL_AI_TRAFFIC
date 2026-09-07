"""모델 종류와 무관한 학습·평가·Artifact 저장 공통 로직."""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sqlalchemy import text

from backend.src.db.database import SessionLocal
from ml.src.util.config import TIME_SPLIT_RATIO
from ml.src.util.paths import LEADERBOARD_PATH


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


def save_report_csv(path: Path, report: dict[str, Any]) -> None:
    """학습·평가 결과를 한 행의 CSV 리포트로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(report)
    if isinstance(row.get("feature_columns"), list):
        row["feature_columns"] = json.dumps(row["feature_columns"], ensure_ascii=False)
    if isinstance(row.get("hyperparameters"), dict):
        row["hyperparameters"] = json.dumps(row["hyperparameters"], ensure_ascii=False)
    pd.DataFrame([row]).to_csv(path, index=False, encoding="utf-8-sig")


def append_leaderboard(report: dict[str, Any], accepted: bool) -> None:
    """모델 학습 시도 결과를 leaderboard CSV에 누적합니다."""
    row = dict(report)
    row["accepted"] = accepted
    row["trained_at"] = datetime.now().isoformat(timespec="seconds")
    if isinstance(row.get("feature_columns"), list):
        row["feature_columns"] = json.dumps(row["feature_columns"], ensure_ascii=False)
    if isinstance(row.get("hyperparameters"), dict):
        row["hyperparameters"] = json.dumps(row["hyperparameters"], ensure_ascii=False)

    LEADERBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_row = pd.DataFrame([row])
    if LEADERBOARD_PATH.exists():
        history = pd.read_csv(LEADERBOARD_PATH)
        new_row = pd.concat([history, new_row], ignore_index=True)
    new_row.sort_values("rmse", ascending=True).to_csv(
        LEADERBOARD_PATH, index=False, encoding="utf-8-sig"
    )


def is_better_than_existing(report_path: Path, metrics: dict[str, float]) -> bool:
    """기존 리포트보다 RMSE가 낮을 때만 새 모델을 채택합니다."""
    report_candidates = [report_path]
    legacy_report = report_path.parent.parent / "ml_models" / report_path.name.replace(
        "_report.csv", "_metrics.json"
    )
    if legacy_report != report_path:
        report_candidates.append(legacy_report)
    existing_report = next((path for path in report_candidates if path.exists()), None)
    if existing_report is None:
        return True

    try:
        if existing_report.suffix == ".json":
            previous_rmse = float(json.loads(existing_report.read_text(encoding="utf-8"))["rmse"])
        else:
            previous = pd.read_csv(existing_report).iloc[0]
            previous_rmse = float(previous["rmse"])
        return metrics["rmse"] < previous_rmse
    except (KeyError, IndexError, ValueError, TypeError, json.JSONDecodeError):
        # 기존 리포트가 없거나 형식이 다르면 새 결과를 정상 결과로 취급합니다.
        return True


def save_if_better(
    *,
    model: Any,
    artifact_path: Path,
    report_path: Path,
    report: dict[str, Any],
    no_db: bool,
) -> bool:
    """새 모델 성능이 개선된 경우에만 파일과 모델 레지스트리를 갱신합니다."""
    accepted = is_better_than_existing(report_path, report)
    append_leaderboard(report, accepted)
    if not accepted:
        if not no_db:
            register_training_history(report=report, artifact_path=artifact_path, accepted=False)
        return False

    save_artifact(model, artifact_path)
    save_report_csv(report_path, report)
    if not no_db:
        register_training_history(report=report, artifact_path=artifact_path, accepted=True)
        register_model_version(
            model_version=report["model_version"],
            algorithm=report["algorithm"],
            hyperparameters=report["hyperparameters"],
            metrics=report,
            artifact_path=artifact_path,
            trained_at=datetime.now(),
        )
    return True


def register_training_history(*, report: dict[str, Any], artifact_path: Path, accepted: bool) -> None:
    """모든 학습 시도 결과를 DB 이력 테이블에 저장합니다."""
    db = SessionLocal()
    try:
        db.execute(text("""
            INSERT INTO model_training_history (
                model_version, algorithm, hyperparameters, mae, rmse, r2_score,
                artifact_path, trained_at, accepted
            ) VALUES (
                :model_version, :algorithm, :hyperparameters, :mae, :rmse, :r2_score,
                :artifact_path, :trained_at, :accepted
            )
        """), {
            "model_version": report["model_version"],
            "algorithm": report["algorithm"],
            "hyperparameters": json.dumps(report["hyperparameters"], ensure_ascii=False),
            "mae": report["mae"],
            "rmse": report["rmse"],
            "r2_score": report["r2"],
            "artifact_path": str(artifact_path),
            "trained_at": datetime.now(),
            "accepted": accepted,
        })
        db.commit()
    finally:
        db.close()


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
        db.execute(text("UPDATE model_versions SET is_active = FALSE"))
        best_version = db.execute(text("""
            SELECT model_version
            FROM model_versions
            ORDER BY rmse ASC, r2_score DESC
            LIMIT 1
        """)).scalar_one_or_none()
        if best_version:
            db.execute(text("""
                UPDATE model_versions
                SET is_active = TRUE
                WHERE model_version = :model_version
            """), {"model_version": best_version})
        db.commit()
    finally:
        db.close()


def main() -> None:
    """모든 모델 또는 지정한 모델을 학습하는 통합 CLI."""
    parser = argparse.ArgumentParser(description="Train RoadPulse ML models")
    parser.add_argument(
        "--model",
        choices=("all", "xgboost", "lightgbm"),
        default="all",
        help="학습할 모델. 기본값은 all",
    )
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--nrows", type=int, default=None)
    parser.add_argument("--no-db", action="store_true", help="DB model registry 저장 생략")
    args = parser.parse_args()

    from ml.src.models.lightgbm_model import train_model as train_lightgbm
    from ml.src.models.xgboost_model import train_model as train_xgboost

    trainers = {
        "xgboost": train_xgboost,
        "lightgbm": train_lightgbm,
    }
    selected = trainers.values() if args.model == "all" else (trainers[args.model],)
    for trainer in selected:
        trainer(input_path=args.input, nrows=args.nrows, no_db=args.no_db)


if __name__ == "__main__":
    main()
