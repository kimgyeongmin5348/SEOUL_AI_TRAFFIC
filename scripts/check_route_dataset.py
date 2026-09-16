"""경로 학습 데이터셋의 정의서 §6 원칙(시간 누수 없음, 요청 단위 보존, 품질 컬럼)을 검사합니다.

위반이 하나라도 있으면 종료 코드 1로 끝나므로 데이터셋 생성 뒤 반드시 실행합니다.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_DATASET = PROJECT_ROOT / "data" / "processed" / "route_training_dataset.csv"
DEFAULT_META = PROJECT_ROOT / "data" / "processed" / "route_feature_meta.json"


def check_dataset(frame, meta):
    """검사 결과 (위반 목록, 요약 dict)를 반환합니다."""
    problems, summary = [], {}
    departure = pd.to_datetime(frame["departure_at"])

    # 1) 시간 누수: 피처가 참조한 관측 시각은 모두 출발 시각 이전이어야 한다.
    for column in meta["feature_timestamp_columns"]:
        if column not in frame.columns:
            problems.append(f"{column} 컬럼 없음")
            continue
        observed = pd.to_datetime(frame[column])
        leaked = int((observed > departure).sum())
        summary[f"leak_{column}"] = leaked
        if leaked:
            problems.append(f"{column}: 출발 이후 관측을 피처로 쓴 행 {leaked}개")

    # 2) 라벨은 주행 시간대 관측이어야 한다: 라벨 관측 최댓값이 출발 - 60분보다 앞서면 안 된다.
    labelled = frame[frame["actual_duration_sec"].notna()]
    if "label_observed_at_max" in frame.columns:
        label_max = pd.to_datetime(labelled["label_observed_at_max"])
        stale = int((label_max < pd.to_datetime(labelled["departure_at"]) - pd.Timedelta(minutes=60)).sum())
        summary["label_stale_rows"] = stale
        if stale:
            problems.append(f"라벨 관측이 출발 60분 이전뿐인 행 {stale}개")

    # 3) 라벨·품질 일관성
    missing_columns = [c for c in meta["feature_columns"] + meta["label_columns"] + meta["quality_columns"] if c not in frame.columns]
    if missing_columns:
        problems.append(f"메타데이터에 있는 컬럼이 데이터셋에 없음: {missing_columns}")
    unusable_with_label = int(((frame["actual_duration_quality"] == "unusable") & frame["actual_duration_sec"].notna()).sum())
    if unusable_with_label:
        problems.append(f"unusable인데 라벨이 있는 행 {unusable_with_label}개")
    usable_without_label = int(((frame["actual_duration_quality"] != "unusable") & frame["actual_duration_sec"].isna()).sum())
    if usable_without_label:
        problems.append(f"품질 등급이 있는데 라벨이 없는 행 {usable_without_label}개")
    if (labelled["observed_length_ratio"] < 0.3).any():
        problems.append("관측 설명 길이 비율 0.3 미만인데 라벨이 있는 행 존재")

    # 4) 요청 단위 보존: 순위는 라벨 있는 후보 2개 이상일 때만, 1..N 연속, chosen_best는 정확히 1개.
    for request_id, group in frame.groupby("route_request_id"):
        ranked = group[group["route_rank_actual"].notna()]
        if ranked.empty:
            continue
        if len(ranked) < 2:
            problems.append(f"{request_id}: 후보 1개에 순위가 있음")
        if sorted(ranked["route_rank_actual"].astype(int)) != list(range(1, len(ranked) + 1)):
            problems.append(f"{request_id}: 순위가 1..N이 아님")
        if int(ranked["chosen_best"].astype(bool).sum()) != 1:
            problems.append(f"{request_id}: chosen_best가 1개가 아님")
        best = ranked.loc[ranked["route_rank_actual"].astype(int).idxmin(), "actual_duration_sec"]
        if best != ranked["actual_duration_sec"].min():
            problems.append(f"{request_id}: 1순위가 최소 통행시간이 아님")
        if group["departure_at"].nunique() != 1:
            problems.append(f"{request_id}: 한 요청에 출발 시각이 여러 개")

    # 5) 요약
    summary.update({
        "rows": len(frame), "requests": int(frame["route_request_id"].nunique()),
        "labelled_rows": len(labelled),
        "ranked_requests": int(frame[frame["route_rank_actual"].notna()]["route_request_id"].nunique()),
        "quality_counts": frame["actual_duration_quality"].value_counts().to_dict(),
        "feature_null_ratio": {c: round(float(frame[c].isna().mean()), 3) for c in meta["feature_columns"] if c in frame.columns and frame[c].isna().any()},
    })
    return problems, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--meta", type=Path, default=DEFAULT_META)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    problems, summary = check_dataset(frame, meta)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if problems:
        print("\nVIOLATIONS:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\nOK: 시간 누수 없음, 요청 단위·라벨·품질 일관성 통과")


if __name__ == "__main__":
    main()
