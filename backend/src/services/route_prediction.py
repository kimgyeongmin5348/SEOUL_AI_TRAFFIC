"""Rank OSRM candidates using the best saved traffic-volume model.

Travel time remains OSRM's estimate. Ranking cost is an explicitly labelled
volume-growth penalty, not a learned ETA or a measured road capacity.
"""
import json
import math
import re
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "ml" / "artifacts"
WEATHER = ["temperature_c", "rainfall_mm", "humidity_pct", "wind_speed_ms", "pressure_hpa"]


def best_saved_model(root=ARTIFACTS):
    reports = {}
    for path in (root / "ml_models").glob("*_metrics.json"):
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        reports[row["model_version"]] = row
    for path in (root / "reports").glob("*_report.csv"):
        row = pd.read_csv(path).iloc[0].to_dict()
        row["feature_columns"] = json.loads(row["feature_columns"])
        reports[row["model_version"]] = row
    candidates = []
    for version, row in reports.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", version):
            continue
        artifact = root / "ml_models" / f"{version}.joblib"
        if artifact.exists() and math.isfinite(float(row["rmse"])):
            candidates.append((row, artifact))
    if not candidates:
        raise ValueError("사용 가능한 학습 모델이 없습니다.")
    # Compare the same validation window only; attempts rejected by training
    # never supersede the report associated with the saved artifact.
    windows = {(r.get("cutoff_time"), r.get("validation_rows"), r.get("split")) for r, _ in candidates}
    if len(windows) != 1:
        raise ValueError("모델 평가 구간이 달라 베스트 모델을 비교할 수 없습니다.")
    report, artifact = min(candidates, key=lambda item: (float(item[0]["rmse"]), -float(item[0]["r2"])))
    model = load_model(str(artifact), artifact.stat().st_mtime_ns)
    return model, report


@lru_cache(maxsize=4)
def load_model(path, modified):
    return joblib.load(path)


def build_features(history, weather, target):
    """Exact hourly lags; never substitute stale rows for missing hours."""
    if not weather or any(weather.get(k) is None for k in WEATHER):
        raise ValueError("예측에 필요한 기상 관측값이 부족합니다.")
    frame = pd.DataFrame(history)
    if frame.empty:
        raise ValueError("최근 교통량 관측값이 없습니다.")
    frame["measured_at"] = pd.to_datetime(frame["measured_at"])
    rows, metadata = [], []
    for (spot, direction), group in frame.groupby(["spot_id", "direction_code"]):
        volumes = group.set_index("measured_at")["volume"].astype(float)
        hours = [target - timedelta(hours=h) for h in range(1, 25)]
        if not all(h in volumes.index for h in hours):
            continue
        past = volumes.loc[hours]
        if not np.isfinite(past).all() or (past < 0).any():
            continue
        last = group.iloc[-1]
        if pd.isna(last["tm_x"]) or pd.isna(last["tm_y"]):
            continue
        day = target.weekday()
        row = {k: float(weather[k]) for k in WEATHER}
        row.update(direction_code=int(direction), tm_x=float(last["tm_x"]), tm_y=float(last["tm_y"]),
                   hour=target.hour, dayofweek=day, is_weekend=int(day >= 5), month=target.month,
                   day=target.day, is_rush_hour=int(day < 5 and target.hour in [7, 8, 9, 18, 19, 20]),
                   hour_sin=math.sin(2*math.pi*target.hour/24), hour_cos=math.cos(2*math.pi*target.hour/24),
                   day_sin=math.sin(2*math.pi*day/7), day_cos=math.cos(2*math.pi*day/7),
                   vol_lag_1h=past.iloc[0], vol_lag_2h=past.iloc[1], vol_lag_24h=past.iloc[23],
                   vol_rolling_mean_3h=past.iloc[:3].mean(), vol_rolling_mean_24h=past.mean())
        rows.append(row)
        metadata.append({"spot_id": spot, "spot_name": last["spot_name"], "baseline": float(past.iloc[23]), "direction_code": int(direction), "tm_x": float(last["tm_x"]), "tm_y": float(last["tm_y"])})
    if not rows:
        raise ValueError("최근 24시간의 연속 교통량이 부족해 AI 추천을 계산할 수 없습니다.")
    return pd.DataFrame(rows), metadata


def road_key(name):
    return re.split(r"[(/]", name)[0].strip().replace(" ", "")


def rank_candidates(candidates, predictions, metadata):
    roads = {}
    for prediction, meta in zip(predictions, metadata, strict=True):
        if not math.isfinite(float(prediction)):
            raise ValueError("모델이 유효하지 않은 예측값을 반환했습니다.")
        # A zero previous-day count cannot support a meaningful growth ratio.
        if meta["baseline"] <= 0:
            continue
        roads.setdefault(road_key(meta["spot_name"]), []).append((max(0., float(prediction)), meta["baseline"]))
    results = []
    for candidate in candidates:
        total = sum(s.duration_sec for s in candidate.steps)
        matched, penalty, predicted, count = 0., 0., 0., 0
        for step in candidate.steps:
            observations = roads.get(road_key(step.name)) if step.name else None
            if not observations:
                continue
            # Both measured directions are pooled: this is a road-level proxy.
            forecast = sum(p for p, _ in observations)
            baseline = sum(b for _, b in observations)
            growth = min(2., max(0., forecast / baseline - 1.))
            matched += step.duration_sec
            penalty += step.duration_sec * growth
            predicted += forecast * step.duration_sec
            count += 1
        coverage = matched / total if total else 0.
        results.append({"id": candidate.id, "coverage": round(coverage, 3),
                        "score": round(candidate.duration_sec * (1 + penalty / total), 2) if total else candidate.duration_sec,
                        "predicted_volume": round(predicted / matched, 1) if matched else None,
                        "matched_steps": count, "ai": False})
    # Incomplete candidates must not win simply because they have no penalty.
    comparable = all(r["coverage"] >= .5 for r in results)
    if comparable:
        min(results, key=lambda r: r["score"])["ai"] = True
    return results, comparable


def predict_routes(db, candidates, now, departure_at=None):
    model, report = best_saved_model()
    target_clock = departure_at or now
    target = target_clock.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    observation_clock = now.replace(tzinfo=None)
    names = {road_key(step.name) for candidate in candidates for step in candidate.steps if step.name}
    spots = db.execute(text("SELECT spot_id, spot_name FROM traffic_spots")).mappings()
    spot_ids = [s["spot_id"] for s in spots if road_key(s["spot_name"]) in names]
    if not spot_ids:
        raise ValueError("경로 도로명에 대응하는 교통량 관측 지점이 없어 AI 추천을 보류했습니다.")
    history = list(db.execute(text("""
        SELECT v.spot_id, s.spot_name, s.tm_x, s.tm_y, v.direction_code,
               v.measured_at, SUM(v.traffic_volume) AS volume
        FROM traffic_volume_measurements v JOIN traffic_spots s ON s.spot_id=v.spot_id
        WHERE v.spot_id IN :spot_ids AND v.measured_at >= :start AND v.measured_at < :target
        GROUP BY v.spot_id, s.spot_name, s.tm_x, s.tm_y, v.direction_code, v.measured_at
        ORDER BY v.measured_at
    """).bindparams(bindparam("spot_ids", expanding=True)), {"spot_ids": spot_ids, "start": target-timedelta(hours=27), "target": target}).mappings())
    weather = db.execute(text("""
        SELECT temperature_c, rainfall_mm, humidity_pct, wind_speed_ms, pressure_hpa, observed_at
        FROM weather_measurements WHERE weather_station_id='108'
        AND observed_at <= :now AND observed_at >= :start
        ORDER BY observed_at DESC LIMIT 1
    """), {"now": target, "start": target-timedelta(hours=36)}).mappings().first()
    if not history:
        raise ValueError("최근 교통량 관측값이 없습니다. 수집 데이터를 갱신해 주세요.")
    observed = max(row["measured_at"] for row in history)
    if observation_clock - observed > timedelta(hours=3):
        raise ValueError("교통량 관측이 3시간 이상 지연되어 AI 추천을 보류했습니다. 수집 데이터를 갱신해 주세요.")
    # VolInfo is published about two hours late. Recursively predict missing
    # hours with the same trained model, instead of pretending old lags are current.
    records = [dict(row) for row in history]
    forecast_target = observed + timedelta(hours=1)
    columns = report["feature_columns"]
    forecast_steps = 0
    while forecast_target <= target:
        features, metadata = build_features(records, weather, forecast_target)
        if set(columns) - set(features.columns):
            raise ValueError("학습 모델의 입력 특성과 현재 추론 특성이 다릅니다.")
        predictions = np.asarray(model.predict(features[columns]), dtype=float)
        if not np.isfinite(predictions).all():
            raise ValueError("모델이 유효하지 않은 예측값을 반환했습니다.")
        for value, meta in zip(predictions, metadata, strict=True):
            records.append({**meta, "measured_at": forecast_target, "volume": max(0., float(value))})
        forecast_target += timedelta(hours=1)
        forecast_steps += 1
    results, comparable = rank_candidates(candidates, predictions, metadata)
    return {"model_version": report["model_version"], "algorithm": report["algorithm"],
            "rmse": float(report["rmse"]), "target_at": target.isoformat()+"+09:00",
            "available": comparable, "routes": results,
            "observed_at": observed.isoformat()+"+09:00",
            "weather_at": weather["observed_at"].isoformat()+"+09:00", "forecast_steps": forecast_steps,
            "message": f"베스트 모델 교통량 예측 반영 · {forecast_steps}시간 순차 예측 · 기상 {weather['observed_at']:%m/%d %H시} 관측 유지 · 도로명 기준 양방향 합산 · 소요시간은 OSRM 추정치" if comparable
            else "경로별 예측 반영 범위가 50% 미만인 구간이 있어 AI 추천을 보류했습니다."}
