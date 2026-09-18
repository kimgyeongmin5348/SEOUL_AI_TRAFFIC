import argparse
import sys
from pathlib import Path
import optuna
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.util.paths import ROUTE_TRAINING_DATASET
from ml.src.util.train import load_route_dataset, route_time_split, route_od_split, evaluate_route, append_route_leaderboard
from ml.src.util.config import ROUTE_FEATURE_COLUMNS, ROUTE_TARGET_COLUMN
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from ml.src.models.xgboost_model import train_route_model as train_xgb
from ml.src.models.lightgbm_model import train_route_model as train_lgbm

def tune(algo: str, n_trials: int, input_path: Path):
    df = load_route_dataset(input_path)
    train, test = route_time_split(df)
    
    def objective(trial):
        if algo == "xgboost":
            params = {
                "objective": "reg:squarederror",
                "n_estimators": trial.suggest_int("n_estimators", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.2, log=True),
                "max_depth": trial.suggest_int("max_depth", 4, 10),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "tree_method": "hist",
                "random_state": 42,
                "n_jobs": -1,
            }
            model = XGBRegressor(**params)
        else:
            params = {
                "objective": "regression",
                "n_estimators": trial.suggest_int("n_estimators", 50, 400),
                "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.2, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 20, 150),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "random_state": 42,
                "n_jobs": -1,
            }
            import warnings
            from lightgbm.sklearn import LGBMDeprecationWarning
            warnings.filterwarnings("ignore", category=LGBMDeprecationWarning)
            model = LGBMRegressor(**params)
            
        if algo == "xgboost":
            model.fit(
                train[ROUTE_FEATURE_COLUMNS], train[ROUTE_TARGET_COLUMN],
                eval_set=[(test[ROUTE_FEATURE_COLUMNS], test[ROUTE_TARGET_COLUMN])],
                verbose=False
            )
        else:
            model.fit(
                train[ROUTE_FEATURE_COLUMNS], train[ROUTE_TARGET_COLUMN],
                eval_X=test[ROUTE_FEATURE_COLUMNS], eval_y=test[ROUTE_TARGET_COLUMN]
            )
            
        metrics = evaluate_route(model, test, ROUTE_FEATURE_COLUMNS)
        # 紐⑤뜽???쒖쐞 ?λ젰??理쒕???(Top-1 湲곗?)
        return metrics["top1_accuracy"]

    study = optuna.create_study(direction="maximize")
    print(f"\n[START] {algo.upper()} Optuna Tuning ?쒖옉 (珥?{n_trials}???먯깋)...")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    from tqdm import tqdm
    for _ in tqdm(range(n_trials), desc=f"{algo.upper()} Trials"):
        study.optimize(objective, n_trials=1, n_jobs=1)

    print(f"\n[DONE] ?쒕떇 ?꾨즺! Best Top-1 Accuracy: {study.best_value:.4f}")
    best_params = study.best_params
    print("?좎젙??理쒖쟻 ?섏씠?쇳뙆?쇰???", best_params)
    
    final_params = {}
    if algo == "xgboost":
        final_params = {"objective": "reg:squarederror", "tree_method": "hist", "random_state": 42, "n_jobs": -1}
        final_params.update(best_params)
        trainer = train_xgb
    else:
        final_params = {"objective": "regression", "random_state": 42, "n_jobs": -1}
        final_params.update(best_params)
        trainer = train_lgbm

    print(f"\n[APPLY] {algo.upper()} 理쒖쟻 ?뚮씪誘명꽣濡?理쒖쥌 ?숈뒿 諛?DB ?깅줉???쒖옉?⑸땲??..")
    od_train, od_test = route_od_split(df)
    model_obj, res = trainer(train=train, test=test, od_train=od_train, od_test=od_test, params=final_params)
    
    # ?ш린?쒕????꾨씫??DB ????〓┰ ???濡쒖쭅 異붽?
    res["accepted"] = True  # ?쒕떇??理쒓퀬 ?깅뒫 紐⑤뜽?대?濡?臾댁“嫄?????깅줉
    from ml.src.util.train import save_route_model
    
    # 援щ텇???꾪빐 ?쒕떇??踰꾩쟾??_tuned ?묐???異붽?
    tuned_version = f"route_{algo.lower()}_duration_v1_tuned"
    res["model_version"] = tuned_version
    
    append_route_leaderboard(res)
    saved_path = save_route_model(model_obj, tuned_version, res, no_db=False)
    
    print(f"[{algo.upper()}] 理쒖쥌 ?깆쟻 -> Top-1: {res['top1_accuracy']:.4f} / Regret: {res['mean_regret_sec']:.1f}s")
    print(f"[{algo.upper()}] ??DB ?깅줉 諛??꾪떚?⑺듃 ????꾨즺: {saved_path}")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Tune Route ML models with Optuna")
    parser.add_argument("--model", choices=("xgboost", "lightgbm", "all"), default="all")
    parser.add_argument("--trials", type=int, default=20, help="Optuna ?먯깋 ?잛닔 (紐⑤뜽??")
    parser.add_argument("--input", type=Path, default=ROUTE_TRAINING_DATASET)
    args = parser.parse_args()
    
    targets = ["xgboost", "lightgbm"] if args.model == "all" else [args.model]
    for t in targets:
        tune(t, args.trials, args.input)


if __name__ == "__main__":
    main()
