import sys
from pathlib import Path
from xgboost import XGBRegressor

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def train_route_model(
    *,
    train,
    test,
    od_train=None,
    od_test=None,
    params: dict = None,
    no_db: bool = False,
) -> tuple:
    from ml.src.util.config import ROUTE_FEATURE_COLUMNS, ROUTE_TARGET_COLUMN, ROUTE_XGB_PARAMS
    from ml.src.util.train import evaluate_route, route_beats_baseline

    if params is None:
        params = ROUTE_XGB_PARAMS.copy()
    model = XGBRegressor(**params)
    
    model.fit(
        train[ROUTE_FEATURE_COLUMNS], train[ROUTE_TARGET_COLUMN],
        eval_set=[(test[ROUTE_FEATURE_COLUMNS], test[ROUTE_TARGET_COLUMN])],
        verbose=False,
    )

    metrics = evaluate_route(model, test, ROUTE_FEATURE_COLUMNS)

    baseline_model_pred = test["osrm_duration_sec"].to_numpy()
    test_copy = test.copy()
    test_copy["pred_score"] = baseline_model_pred
    from backend.src.services.route_ranking_evaluation import (
        mean_regret, pairwise_ranking_accuracy, top1_accuracy,
    )
    grouped = {}
    for row in test_copy.itertuples():
        grouped.setdefault(row.route_request_id, []).append({
            "route_id": row.route_id,
            "score": float(row.pred_score),
            "actual_duration_sec": float(getattr(row, ROUTE_TARGET_COLUMN)),
        })
    baseline_requests = [{"route_request_id": k, "candidates": v} for k, v in grouped.items()]
    baseline = {
        "baseline_mae": float((test[ROUTE_TARGET_COLUMN] - test["osrm_duration_sec"]).abs().mean()),
        "baseline_top1_accuracy": top1_accuracy(baseline_requests),
        "baseline_pairwise_ranking_accuracy": pairwise_ranking_accuracy(baseline_requests),
        "baseline_mean_regret_sec": mean_regret(baseline_requests),
    }

    adopted = route_beats_baseline(metrics, baseline)

    version = "route_xgb_duration_v1"
    result = {
        "model_version": version,
        "algorithm": "XGBoostRegressor",
        "hyperparameters": params,
        **metrics, **baseline,
        "accepted": adopted,
    }

    if od_train is not None and od_test is not None and not od_train.empty and not od_test.empty:
        od_model = XGBRegressor(**params)
        od_model.fit(od_train[ROUTE_FEATURE_COLUMNS], od_train[ROUTE_TARGET_COLUMN], verbose=False)
        od_metrics = evaluate_route(od_model, od_test, ROUTE_FEATURE_COLUMNS)
        result.update({
            "od_top1_accuracy": od_metrics["top1_accuracy"],
            "od_mean_regret_sec": od_metrics["mean_regret_sec"],
            "od_generalizes": route_beats_baseline(od_metrics, {
                "baseline_top1_accuracy": baseline["baseline_top1_accuracy"],
                "baseline_mean_regret_sec": baseline["baseline_mean_regret_sec"],
                "baseline_mae": baseline["baseline_mae"],
            }),
        })

    return model, result

def main() -> None:
    pass

if __name__ == "__main__":
    main()
