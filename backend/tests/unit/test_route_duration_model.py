"""경로 소요시간 모델 학습 로직 검증."""
import pandas as pd

from ml.src.models.route_duration_model import (
    prepare_dataset,
    ranking_metrics,
    regression_metrics,
    requests_from_predictions,
    time_split,
    train_route_model,
)


def _row(request_id, route_id, departure, actual, distance=1000.0, osrm=100.0,
         segments=5, link_ratio=0.8, direction=None):
    return {
        "route_request_id": request_id, "route_id": route_id,
        "departure_at": departure, "route_distance_m": distance,
        "osrm_duration_sec": osrm, "segment_count": segments,
        "link_match_ratio": link_ratio, "direction_match_ratio": direction,
        "actual_duration_sec": actual,
    }


def test_prepare_dataset_adds_hour_and_fills_direction():
    frame = prepare_dataset(pd.DataFrame([_row("r1", "A", "2026-09-13T08:00:00", 100.0, direction=None)]))
    assert frame["departure_hour"].iloc[0] == 8
    assert frame["direction_match_ratio"].iloc[0] == 0.0


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