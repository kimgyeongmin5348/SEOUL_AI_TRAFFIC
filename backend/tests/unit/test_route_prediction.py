import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.src.api.app import app
from backend.src.services.route_prediction import best_saved_model, build_features, rank_candidates


def candidate(id, duration, road):
    return SimpleNamespace(id=id, duration_sec=duration,
                           steps=[SimpleNamespace(name=road, duration_sec=duration)])


def test_best_saved_artifact_not_rejected_leaderboard_attempt(tmp_path):
    (tmp_path / "reports").mkdir()
    (tmp_path / "ml_models").mkdir()
    for name, rmse in [("xgb", 10), ("lgbm", 20)]:
        (tmp_path / "ml_models" / f"{name}.joblib").touch()
        report = dict(model_version=name, rmse=rmse, r2=.9, feature_columns=["hour"],
                      cutoff_time="2025-01-01", validation_rows=100, split="time")
        (tmp_path / "ml_models" / f"{name}_metrics.json").write_text(json.dumps(report))
    (tmp_path / "reports" / "leaderboard.csv").write_text("model_version,rmse,accepted\nlgbm,1,False")
    with patch("backend.src.services.route_prediction.load_model", return_value=object()):
        _, report = best_saved_model(tmp_path)
    assert report["model_version"] == "xgb"


def test_predictions_change_recommendation_and_incomplete_routes_are_excluded():
    routes = [candidate("A", 600, "강남대로"), candidate("B", 700, "테헤란로")]
    meta = [{"spot_name": "강남대로(강남역)", "baseline": 100},
            {"spot_name": "테헤란로(역삼역)", "baseline": 100}]
    result, ok = rank_candidates(routes, [200, 100], meta)
    assert ok and result[1]["ai"] and not result[0]["ai"]
    result, ok = rank_candidates(routes, [100, 200], meta)
    assert ok and result[0]["ai"]
    result, ok = rank_candidates(routes, [200], meta[:1])
    assert ok and result[0]["ai"] and not result[1]["ai"]
    result, ok = rank_candidates([candidate("B", 700, "테헤란로")], [200], meta[:1])
    assert not ok and not result[0]["ai"]
    with pytest.raises(ValueError):
        rank_candidates(routes, [np.nan, 100], meta)


def test_features_use_exact_lags_and_do_not_mix_directions():
    target = datetime(2026, 9, 10, 9)
    history = [dict(spot_id="A", spot_name="강남대로", tm_x=1, tm_y=2,
                    direction_code=d, measured_at=target-timedelta(hours=h), volume=d*100+h)
               for d in (1, 2) for h in range(1, 25)]
    weather = dict(temperature_c=20, rainfall_mm=0, humidity_pct=50, wind_speed_ms=2, pressure_hpa=1000)
    features, _ = build_features(history, weather, target)
    assert features.vol_lag_1h.tolist() == [101, 201]
    assert features.vol_lag_24h.tolist() == [124, 224]
    assert features.vol_rolling_mean_3h.tolist() == [102, 202]
    assert features.is_rush_hour.tolist() == [1, 1]
    with pytest.raises(ValueError):
        build_features([r for r in history if r["measured_at"] != target-timedelta(hours=2)], weather, target)


def test_features_treat_kma_no_rain_null_as_zero():
    target = datetime(2026, 9, 10, 9)
    history = [dict(spot_id="A", spot_name="강남대로", tm_x=1, tm_y=2,
                    direction_code=1, measured_at=target-timedelta(hours=h), volume=100+h)
               for h in range(1, 25)]
    weather = dict(temperature_c=20, rainfall_mm=None, humidity_pct=50,
                   wind_speed_ms=2, pressure_hpa=1000)
    features, _ = build_features(history, weather, target)
    assert features.rainfall_mm.tolist() == [0.0]


def test_api_validates_duplicate_ids_and_durations():
    client = TestClient(app)
    item = dict(id="A", duration_sec=600, steps=[dict(name="강남대로", duration_sec=600)])
    assert client.post("/api/routes/predict", json={"candidates": [item, item]}).status_code == 422
    item["steps"][0]["duration_sec"] = 10
    assert client.post("/api/routes/predict", json={"candidates": [item]}).status_code == 422


def test_real_saved_model_predicts_with_saved_feature_order():
    model, report = best_saved_model()
    frame = pd.DataFrame([{column: 1. for column in report["feature_columns"]}])
    prediction = model.predict(frame[report["feature_columns"]])
    assert len(prediction) == 1 and np.isfinite(prediction).all()


def test_real_model_with_delayed_observations_reaches_current_hour():
    from unittest.mock import MagicMock
    from backend.src.services.route_prediction import predict_routes
    target = datetime(2026, 9, 10, 9)
    observed = target - timedelta(hours=2)
    history = [dict(spot_id="A", spot_name="강남대로", tm_x=200000, tm_y=450000,
                    direction_code=1, measured_at=observed-timedelta(hours=h), volume=1000+h)
               for h in range(25)]
    weather = dict(temperature_c=20, rainfall_mm=0, humidity_pct=50, wind_speed_ms=2,
                   pressure_hpa=1000, observed_at=target-timedelta(hours=12))
    db = MagicMock()
    spots, traffic, climate = MagicMock(), MagicMock(), MagicMock()
    spots.mappings.return_value = [{"spot_id": "A", "spot_name": "강남대로"}]
    traffic.mappings.return_value = history
    climate.mappings.return_value.first.return_value = weather
    db.execute.side_effect = [spots, traffic, climate]
    result = predict_routes(db, [candidate("A", 600, "강남대로")], target)
    assert result["forecast_steps"] == 2
    assert result["target_at"] == "2026-09-10T09:00:00+09:00"
    assert result["routes"][0]["ai"]
    assert result["routes"][0]["predicted_volume"] >= 0
    db.execute.side_effect = [spots, traffic, climate]
    with pytest.raises(ValueError, match="지연"):
        predict_routes(db, [candidate("A", 600, "강남대로")], target+timedelta(days=1))
