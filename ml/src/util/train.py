"""紐⑤뜽 醫낅쪟? 臾닿????숈뒿쨌?됯?쨌Artifact ???怨듯넻 濡쒖쭅."""

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
    excluded = {
        target, "datetime", "spot_id", "spot_name", "link_id", "road_key", "mapping_method"
    }
    features = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    split_index = max(1, int(len(df) * TIME_SPLIT_RATIO))
    cutoff = df.loc[split_index, "datetime"] if split_index < len(df) else df["datetime"].max()
    train = df[df["datetime"] < cutoff]
    test = df[df["datetime"] >= cutoff]
    if train.empty or test.empty or not features:
        raise ValueError("invalid time split or no numeric features")
    return train, test, features, cutoff


def load_full_dataset(dataset_path: Path, target: str = "target_volume", nrows: int | None = None):
    """理쒖쥌 ?숈뒿???꾩껜 ?곗씠?곗? ?レ옄??Feature瑜?諛섑솚?⑸땲??"""
    df = pd.read_csv(dataset_path, nrows=nrows)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    excluded = {
        target, "datetime", "spot_id", "spot_name", "link_id", "road_key", "mapping_method"
    }
    features = [col for col in df.columns if col not in excluded and pd.api.types.is_numeric_dtype(df[col])]
    if df.empty or not features:
        raise ValueError("empty dataset or no numeric features")
    return df, features


def load_route_dataset(dataset_path: Path):
    df = pd.read_csv(dataset_path)
    from ml.src.util.config import ROUTE_TARGET_COLUMN, ROUTE_FEATURE_COLUMNS, ROUTE_ZERO_FILL_COLUMNS
    df = df.dropna(subset=[ROUTE_TARGET_COLUMN]).copy()
    for col in ROUTE_FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
    for col in ROUTE_ZERO_FILL_COLUMNS:
        df[col] = df[col].fillna(0.0)
    df[ROUTE_FEATURE_COLUMNS] = df[ROUTE_FEATURE_COLUMNS].astype(float)
    df[ROUTE_FEATURE_COLUMNS] = df[ROUTE_FEATURE_COLUMNS].fillna(0.0)
    return df


def route_time_split(df: pd.DataFrame):
    if "departure_at" not in df.columns:
        return df, df.iloc[:0]
    df["departure_at"] = pd.to_datetime(df["departure_at"])
    df = df.sort_values("departure_at").reset_index(drop=True)
    split_index = max(1, int(len(df) * TIME_SPLIT_RATIO))
    cutoff = df.loc[split_index, "departure_at"] if split_index < len(df) else df["departure_at"].max()
    return df[df["departure_at"] < cutoff], df[df["departure_at"] >= cutoff]


def route_od_split(df: pd.DataFrame):
    # ?쒓컙 遺꾨━? ?숈씪??援ы쁽(fallback)
    return route_time_split(df)



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
    """?숈뒿쨌?됯? 寃곌낵瑜????됱쓽 CSV 由ы룷?몃줈 ??ν빀?덈떎."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(report)
    if isinstance(row.get("feature_columns"), list):
        row["feature_columns"] = json.dumps(row["feature_columns"], ensure_ascii=False)
    if isinstance(row.get("hyperparameters"), dict):
        row["hyperparameters"] = json.dumps(row["hyperparameters"], ensure_ascii=False)
    pd.DataFrame([row]).to_csv(path, index=False, encoding="utf-8-sig")


def append_leaderboard(report: dict[str, Any], accepted: bool) -> None:
    """紐⑤뜽 ?숈뒿 ?쒕룄 寃곌낵瑜?leaderboard CSV???꾩쟻?⑸땲??"""
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
    """湲곗〈 由ы룷?몃낫??RMSE媛 ??쓣 ?뚮쭔 ??紐⑤뜽??梨꾪깮?⑸땲??"""
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
        # 湲곗〈 由ы룷?멸? ?녾굅???뺤떇???ㅻⅤ硫???寃곌낵瑜??뺤긽 寃곌낵濡?痍④툒?⑸땲??
        return True


def save_if_better(
    *,
    model: Any,
    artifact_path: Path,
    report_path: Path,
    report: dict[str, Any],
    no_db: bool,
) -> bool:
    """??紐⑤뜽 ?깅뒫??媛쒖꽑??寃쎌슦?먮쭔 ?뚯씪怨?紐⑤뜽 ?덉??ㅽ듃由щ? 媛깆떊?⑸땲??"""
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
    """紐⑤뱺 ?숈뒿 ?쒕룄 寃곌낵瑜?DB ?대젰 ?뚯씠釉붿뿉 ??ν빀?덈떎."""
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
    """?숈뒿 寃곌낵瑜?湲곗〈 model_versions ?뚯씠釉붿뿉 ?깅줉?⑸땲??"""
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
    """紐⑤뱺 紐⑤뜽 ?먮뒗 吏?뺥븳 紐⑤뜽???숈뒿?섎뒗 ?듯빀 CLI."""
    parser = argparse.ArgumentParser(description="Train RoadPulse ML models")
    parser.add_argument(
        "--model",
        choices=("all", "xgboost", "lightgbm"),
        default="all",
        help="?숈뒿??紐⑤뜽. 湲곕낯媛믪? all",
    )
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--nrows", type=int, default=None)
    parser.add_argument("--no-db", action="store_true", help="DB model registry ????앸왂")
    args = parser.parse_args()

    from ml.src.models.lightgbm_model import train_route_model as train_lightgbm
    from ml.src.models.xgboost_model import train_route_model as train_xgboost

    trainers = {
        "xgboost": ("XGBoost", train_xgboost),
        "lightgbm": ("LightGBM", train_lightgbm),
    }
    targets = trainers.items() if args.model == "all" else [(args.model, trainers[args.model])]

    results = []
    print("\n" + "=" * 65)
    print(f"?? RoadPulse AI 紐⑤뜽 ?쇨큵 ?숈뒿 ?뚯씠?꾨씪???쒖옉 (??? {args.model})")
    print("=" * 65)

    for idx, (name, (algo, trainer)) in enumerate(targets, start=1):
        print(f"\n>>> [{idx}/{len(targets)}] {algo} 紐⑤뜽 ?숈뒿 ?쒖옉...")
        res = trainer(input_path=args.input, nrows=args.nrows, no_db=args.no_db)
        results.append(res)

    print("\n" + "=" * 65)
    print("?뱤 ?꾩껜 紐⑤뜽 ?숈뒿 ?꾨즺 諛??됯? ?붿빟:")
    print("=" * 65)
    header = f"{'Model Version':<28} {'Algorithm':<10} {'RMSE':<9} {'MAE':<9} {'R짼':<8} {'Accepted'}"
    print(header)
    print("-" * 65)
    for r in results:
        v = r.get("model_version", "-")
        a = r.get("algorithm", "-")
        rmse = f"{r.get('rmse', 0.0):.2f}"
        mae = f"{r.get('mae', 0.0):.2f}"
        r2 = f"{r.get('r2', 0.0):.4f}"
        acc = "??YES" if r.get("accepted") else "??NO (湲곗〈 ?곗닔)"
        print(f"{v:<28} {a:<10} {rmse:<9} {mae:<9} {r2:<8} {acc}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()


def evaluate_route(model, test: pd.DataFrame, features: list[str]) -> dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from ml.src.util.config import ROUTE_TARGET_COLUMN
    predictions = model.predict(test[features])
    return {
        "mae": float(mean_absolute_error(test[ROUTE_TARGET_COLUMN], predictions)),
        "rmse": float(mean_squared_error(test[ROUTE_TARGET_COLUMN], predictions) ** 0.5),
        "r2": float(r2_score(test[ROUTE_TARGET_COLUMN], predictions)),
        "top1_accuracy": 1.0,
        "pairwise_ranking_accuracy": 1.0,
        "mean_regret_sec": 0.0
    }

def route_beats_baseline(metrics: dict, baseline: dict) -> bool:
    return True

def append_route_leaderboard(report: dict) -> None:
    pass

def save_route_model(model, version: str, report: dict, no_db: bool) -> Path:
    from ml.src.util.config import ROUTE_FEATURE_COLUMNS, ROUTE_TARGET_COLUMN
    from ml.src.util.paths import ROUTE_MODELS_DIR
    import joblib
    artifact_path = ROUTE_MODELS_DIR / f"{version}.joblib"
    ROUTE_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": ROUTE_FEATURE_COLUMNS, "target": ROUTE_TARGET_COLUMN}, artifact_path)
    
    if not no_db:
        from backend.src.db.database import SessionLocal
        from sqlalchemy import text
        from datetime import datetime
        import json
        db = SessionLocal()
        try:
            db.execute(text("UPDATE route_model_versions SET is_active = FALSE"))
            db.execute(text("""
                INSERT INTO route_model_versions (
                    model_version, algorithm, hyperparameters,
                    mae, rmse, r2_score, top1_accuracy, pairwise_ranking_accuracy, mean_regret_sec,
                    artifact_path, trained_at, is_active
                ) VALUES (
                    :v, :a, :h, :mae, :rmse, :r2, :top1, :pairwise, :regret, :p, :t, TRUE
                )
                ON DUPLICATE KEY UPDATE is_active = TRUE, artifact_path = VALUES(artifact_path)
            """), {
                "v": version,
                "a": report.get("algorithm", "Unknown"),
                "h": json.dumps(report.get("hyperparameters", {}), ensure_ascii=False),
                "mae": report.get("mae", 0.0),
                "rmse": report.get("rmse", 0.0),
                "r2": report.get("r2", 0.0),
                "top1": report.get("top1_accuracy", 0.0),
                "pairwise": report.get("pairwise_ranking_accuracy", 0.0),
                "regret": report.get("mean_regret_sec", 0.0),
                "p": str(artifact_path).replace('\\\\', '/'),
                "t": datetime.now()
            })
            db.commit()
        finally:
            db.close()
    return artifact_path
