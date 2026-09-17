"""경로 소요시간 모델 학습 로직 검증."""
import pandas as pd

from ml.src.models.route_duration_model import (
    baseline_metrics,
    beats_baseline,
    od_split,
    prepare_dataset,
    ranking_metrics,
    regression_metrics,
    requests_from_predictions,
    time_split,
    train_route_model,
)


def _row(request_id, route_id, departure, actual, distance=1000.0, osrm=100.0,
         segments=5, link_ratio=0.8, direction=None, origin="서울역", destination="강남역"):
    return {
        "route_request_id": request_id, "route_id": route_id,
        "origin_name": origin, "destination_name": destination,
        "departure_at": departure, "route_distance_m": distance,
        "osrm_duration_sec": osrm, "segment_count": segments,
        "link_match_ratio": link_ratio, "direction_match_ratio": direction,
        "actual_duration_sec": actual,
    }


def test_prepare_dataset_adds_calendar_features_fills_ratios_and_drops_unlabelled():
    frame = prepare_dataset(pd.DataFrame([
        _row("r1", "A", "2026-09-13T08:00:00", 100.0, direction=None),
        _row("r1", "B", "2026-09-13T08:00:00", None),  # unusable 라벨 → 제외
    ]))
    assert len(frame) == 1
    assert frame["departure_hour"].iloc[0] == 8 and frame["weekday"].iloc[0] == 6 and frame["is_weekend"].iloc[0] == 1
    assert frame["direction_match_ratio"].iloc[0] == 0.0
    # 데이터셋에 없는 속도·기상 피처는 NaN으로 남아 모델이 결측을 구분합니다.
    assert pd.isna(frame["speed_lag_kmh"].iloc[0])


def test_time_split_keeps_order_and_splits_by_time():
    rows = [
        _row("r1", "A", "2026-09-13T08:00:00", 100.0),
        _row("r2", "A", "2026-09-13T09:00:00", 110.0),
        _row("r3", "A", "2026-09-13T10:00:00", 120.0),
        _row("r4", "A", "2026-09-13T11:00:00", 130.0),
    ]
    train, test = time_split(prepare_dataset(pd.DataFrame(rows)), ratio=0.5)
    assert len(train) == 2 and len(test) == 2
    assert train["departure_at"].max() < test["departure_at"].min()


def test_regression_metrics_perfect_prediction():
    metrics = regression_metrics([100.0, 200.0], [100.0, 200.0])
    assert metrics["mae"] == 0.0
    assert metrics["rmse"] == 0.0


def test_requests_from_predictions_uses_predicted_duration_as_cost():
    # 비용 점수는 예측 통행시간 그대로이며, 낮을수록 우수한 후보입니다.
    frame = prepare_dataset(pd.DataFrame([
        _row("r1", "A", "2026-09-13T08:00:00", 100.0),
        _row("r1", "B", "2026-09-13T08:00:00", 200.0),
    ]))
    requests = requests_from_predictions(frame, [150.0, 90.0])
    candidates = {c["route_id"]: c for c in requests[0]["candidates"]}
    assert candidates["B"]["score"] == 90.0
    assert candidates["A"]["score"] == 150.0


def test_ranking_metrics_top1_correct():
    requests = [{"route_request_id": "r1", "candidates": [
        {"route_id": "A", "score": 100.0, "actual_duration_sec": 100.0},
        {"route_id": "B", "score": 200.0, "actual_duration_sec": 200.0},
    ]}]
    metrics = ranking_metrics(requests)
    assert metrics["top1_accuracy"] == 1.0
    assert metrics["pairwise_ranking_accuracy"] == 1.0
    assert metrics["mean_regret_sec"] == 0.0


def test_train_route_model_reports_insufficient_data(tmp_path):
    dataset = tmp_path / "small.csv"
    pd.DataFrame([_row("r1", "A", "2026-09-13T08:00:00", 100.0)]).to_csv(dataset, index=False)
    result = train_route_model(dataset, tmp_path, min_rows=50)
    assert result["status"] == "insufficient_data"
    assert result["rows"] == 1

def test_baseline_metrics_and_adoption_rule():
    test = prepare_dataset(pd.DataFrame([
        _row("r1", "A", "2026-09-13T08:00:00", 300.0, osrm=100.0),
        _row("r1", "B", "2026-09-13T08:00:00", 200.0, osrm=120.0),  # OSRM은 A를 고르지만 실제로는 B가 빠름
    ]))
    baseline = baseline_metrics(test)
    assert baseline["baseline_top1_accuracy"] == 0.0 and baseline["baseline_mean_regret_sec"] == 100.0
    better = {"mae": 10.0, "top1_accuracy": 1.0, "mean_regret_sec": 0.0}
    worse = {"mae": 300.0, "top1_accuracy": 0.0, "mean_regret_sec": 100.0}
    assert beats_baseline(better, baseline) is True
    assert beats_baseline(worse, baseline) is False
    assert beats_baseline({"mae": 10.0, "top1_accuracy": None, "mean_regret_sec": None}, baseline) is False


def test_od_split_keeps_whole_od_pairs_on_one_side():
    rows = []
    for index, (o, d) in enumerate([("서울역", "강남역"), ("잠실", "광화문"), ("홍대", "여의도"), ("노원", "서울역")]):
        for route_id in "AB":
            rows.append(_row(f"r{index}", route_id, "2026-09-13T08:00:00", 100.0, origin=o, destination=d))
    frame = prepare_dataset(pd.DataFrame(rows))
    train, test = od_split(frame, holdout_ratio=0.25)
    assert len(test) == 2 and len(train) == 6
    train_pairs = set(zip(train["origin_name"], train["destination_name"]))
    test_pairs = set(zip(test["origin_name"], test["destination_name"]))
    assert train_pairs.isdisjoint(test_pairs)
