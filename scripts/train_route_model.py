"""경로 소요시간 회귀 모델을 학습하는 CLI.

데이터가 충분하지 않으면 아티팩트를 채택하지 않습니다. --force로 강제 학습할 수 있습니다.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.models.route_duration_model import train_route_model

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "route_training_dataset.csv"
DEFAULT_ARTIFACTS = PROJECT_ROOT / "ml" / "artifacts"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--min-rows", type=int, default=50, help="아티팩트 채택 최소 행 수")
    parser.add_argument("--force", action="store_true", help="데이터가 적어도 강제 학습")
    args = parser.parse_args()

    result = train_route_model(args.input, args.artifacts, min_rows=args.min_rows, force=args.force)
    if result["status"] in ("trained", "not_adopted"):
        print(f"model_version: {result['model_version']}")
        print(f"rows: {result['rows']} (train {result['train_rows']} / holdout {result['holdout_rows']}, "
              f"holdout requests {result['holdout_requests']})")
        print(f"model    MAE {result['mae']:.2f} RMSE {result['rmse']:.2f} R2 {result['r2']:.4f} | "
              f"Top-1 {result['top1_accuracy']} pairwise {result['pairwise_ranking_accuracy']} regret {result['mean_regret_sec']}")
        print(f"baseline MAE {result['baseline_mae']:.2f} RMSE {result['baseline_rmse']:.2f} R2 {result['baseline_r2']:.4f} | "
              f"Top-1 {result['baseline_top1_accuracy']} pairwise {result['baseline_pairwise_ranking_accuracy']} regret {result['baseline_mean_regret_sec']}")
        if "od_top1_accuracy" in result:
            print(f"OD holdout ({result['od_holdout_pairs']} pairs, {result['od_holdout_rows']} rows): "
                  f"model Top-1 {result['od_top1_accuracy']} regret {result['od_mean_regret_sec']} MAE {result['od_mae']:.2f} | "
                  f"baseline Top-1 {result['od_baseline_top1_accuracy']} regret {result['od_baseline_mean_regret_sec']} "
                  f"MAE {result['od_baseline_mae']:.2f} | generalizes={result['od_generalizes']}")
    if result["status"] == "trained":
        print(f"artifact: {result['artifact']}")
    else:
        print(f"[{result['status']}] {result['message']}")


if __name__ == "__main__":
    main()