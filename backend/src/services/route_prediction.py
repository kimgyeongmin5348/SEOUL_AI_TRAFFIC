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
from pyproj import Transformer
from sqlalchemy import bindparam, text

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = ROOT / "ml" / "artifacts"
WEATHER = ["temperature_c", "rainfall_mm", "humidity_pct", "wind_speed_ms", "pressure_hpa"]
TM_TO_WGS84 = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)


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


def build_features(history, weather, target, speed_history=None):
    """Build lag features from fresh observations plus a 30-day hourly profile.

    The trained artifact still receives the same columns it was trained with,
    while a single missing collection hour no longer disables inference.
    """
    if not weather:
        raise ValueError("예측에 필요한 기상 관측값이 부족합니다.")
    weather = dict(weather)
    # KMA represents an hour without precipitation as NULL.  For model input
    # that is a measured zero, while NULL for every other feature is missing.
    if weather.get("rainfall_mm") is None:
        weather["rainfall_mm"] = 0.0
    if any(weather.get(k) is None for k in WEATHER):
        raise ValueError("예측에 필요한 기상 관측값이 부족합니다.")
    frame = pd.DataFrame(history)
    if frame.empty:
        raise ValueError("최근 교통량 관측값이 없습니다.")
    frame["measured_at"] = pd.to_datetime(frame["measured_at"])
    rows, metadata = [], []
    speed_frame = pd.DataFrame(
        speed_history or [],
        columns=["spot_id", "measured_at", "speed_kmh", "travel_time_sec"],
    )
    if not speed_frame.empty:
        speed_frame["measured_at"] = pd.to_datetime(speed_frame["measured_at"])
    for (spot, direction), group in frame.groupby(["spot_id", "direction_code"]):
        group = group.sort_values("measured_at")
        volumes = group.set_index("measured_at")["volume"].astype(float)
        hours = [target - timedelta(hours=h) for h in range(1, 25)]

        def observed_or_profile(moment):
            if moment in volumes.index:
                value = volumes.loc[moment]
                if np.isscalar(value):
                    return float(value)
                return float(value.iloc[-1])
            same_hour = volumes[(volumes.index.hour == moment.hour) & (volumes.index < target)]
            valid = same_hour[np.isfinite(same_hour) & (same_hour >= 0)]
            return float(valid.median()) if not valid.empty else math.nan

        past = pd.Series([observed_or_profile(hour) for hour in hours], index=hours)
        if not np.isfinite(past).all() or (past < 0).any():
            continue
        last = group.iloc[-1]
        if pd.isna(last["tm_x"]) or pd.isna(last["tm_y"]):
            continue
        day = target.weekday()
        row = {k: float(weather[k]) for k in WEATHER}
        speed_row = speed_frame[
            (speed_frame["spot_id"] == spot)
            & (speed_frame["measured_at"] <= target - timedelta(hours=1))
        ].sort_values("measured_at").tail(1)
        row["speed_lag_1h"] = float(speed_row["speed_kmh"].iloc[0]) if not speed_row.empty else math.nan
        row["travel_time_lag_1h"] = float(speed_row["travel_time_sec"].iloc[0]) if not speed_row.empty else math.nan
        row["speed_data_available"] = int(not speed_row.empty)
        row.update(direction_code=int(direction), tm_x=float(last["tm_x"]), tm_y=float(last["tm_y"]),
                   hour=target.hour, dayofweek=day, is_weekend=int(day >= 5), month=target.month,
                   day=target.day, is_rush_hour=int(day < 5 and target.hour in [7, 8, 9, 18, 19, 20]),
                   hour_sin=math.sin(2*math.pi*target.hour/24), hour_cos=math.cos(2*math.pi*target.hour/24),
                   day_sin=math.sin(2*math.pi*day/7), day_cos=math.cos(2*math.pi*day/7),
                   vol_lag_1h=past.iloc[0], vol_lag_2h=past.iloc[1], vol_lag_24h=past.iloc[23],
                   vol_rolling_mean_3h=past.iloc[:3].mean(), vol_rolling_mean_24h=past.mean())
        rows.append(row)
        typical = volumes[
            (volumes.index.weekday == target.weekday())
            & (volumes.index.hour == target.hour)
            & (volumes.index < target)
        ]
        typical = typical[np.isfinite(typical) & (typical >= 0)]
        metadata.append({
            "spot_id": spot,
            "spot_name": last["spot_name"],
            "baseline": float(past.iloc[23]),
            "typical_volume": float(typical.median()) if not typical.empty else float(past.iloc[23]),
            "direction_code": int(direction),
            "tm_x": float(last["tm_x"]),
            "tm_y": float(last["tm_y"]),
        })
    if not rows:
        raise ValueError("실시간 교통량과 최근 시간대별 이력이 부족해 AI 추천을 계산할 수 없습니다.")
    return pd.DataFrame(rows), metadata


def road_key(name):
    return re.split(r"[(/]", name)[0].strip().replace(" ", "")


def load_active_incidents(db, departure_at):
    # 출발 시각에 살아 있는 돌발만 먼저 조회해 과거 사고를 제외합니다.
    rows = db.execute(text("""
         SELECT i.incident_id, i.link_id, i.incident_type, i.incident_detail_type,
             i.occurred_at, i.expected_clear_at, i.description, i.tm_x, i.tm_y,
             r.road_name
        FROM incidents i
        LEFT JOIN road_segments r ON r.link_id = i.link_id
        WHERE i.occurred_at <= :departure_at
          AND (i.expected_clear_at IS NULL OR i.expected_clear_at >= :departure_at)
    """), {"departure_at": departure_at}).mappings()
    by_road = {}
    for incident in rows:
        road_name = incident.get("road_name")
        item = dict(incident)
        if item.get("tm_x") is not None and item.get("tm_y") is not None:
            item["longitude"], item["latitude"] = TM_TO_WGS84.transform(
                float(item["tm_x"]), float(item["tm_y"])
            )
        if road_name:
            by_road.setdefault(road_key(road_name), []).append(item)
    return by_road


def point_to_polyline_distance_m(longitude, latitude, coordinates):
    """Approximate WGS84 point-to-polyline distance for Seoul-scale routes."""
    # 서울 범위에서는 위경도를 국소 미터 좌표로 바꿔 빠르게 계산합니다.
    if longitude is None or latitude is None or len(coordinates) < 2:
        return None
    latitude_scale = 111_320.0
    longitude_scale = latitude_scale * math.cos(math.radians(latitude))
    minimum = math.inf
    for start, end in zip(coordinates, coordinates[1:]):
        start_x = (start[0] - longitude) * longitude_scale
        start_y = (start[1] - latitude) * latitude_scale
        end_x = (end[0] - longitude) * longitude_scale
        end_y = (end[1] - latitude) * latitude_scale
        dx, dy = end_x - start_x, end_y - start_y
        length_squared = dx * dx + dy * dy
        projection = 0.0 if length_squared == 0 else max(
            0.0, min(1.0, -(start_x * dx + start_y * dy) / length_squared)
        )
        distance = math.hypot(start_x + projection * dx, start_y + projection * dy)
        minimum = min(minimum, distance)
    return minimum


def incident_matches_route(incident, coordinates):
    distance = point_to_polyline_distance_m(
        incident.get("longitude"), incident.get("latitude"), coordinates
    )
    return distance is not None and distance <= incident_impact_radius_m(incident)


def incident_category(incident):
    incident_type = str(incident.get("incident_type") or "")
    category = {
        "A01": "accident",
        "A02": "breakdown",
        "A04": "construction",
        "A08": "control",
        "A10": "control",
    }.get(incident_type)
    if category:
        return category
    text_value = " ".join(
        str(incident.get(key) or "")
        for key in ("incident_type", "incident_detail_type", "description")
    ).lower()
    if any(word in text_value for word in ("사고", "추돌", "accident")):
        return "accident"
    if any(word in text_value for word in ("고장", "breakdown")):
        return "breakdown"
    if any(word in text_value for word in ("통제", "차단", "control", "closed")):
        return "control"
    if any(word in text_value for word in ("공사", "보수", "construction")):
        return "construction"
    return "other"


def incident_impact_radius_m(incident):
    return {
        "accident": 180.0,
        "breakdown": 120.0,
        "construction": 150.0,
        "control": 250.0,
        "other": 100.0,
    }[incident_category(incident)]


def incident_penalty_multiplier(incident):
    category = incident_category(incident)
    if category == "control":
        return 5.0
    if category == "accident":
        return 0.5
    if category == "construction":
        return 0.3
    if category == "breakdown":
        return 0.4
    return 0.2


SEOUL_CENTER_LAT = 37.5665
SEOUL_CENTER_LNG = 126.9780


def determine_route_direction(coordinates):
    """OSRM polyline 시작/끝 좌표로 도심 유입(1, Inbound) 또는 외곽 유출(2, Outbound)을 판정합니다."""
    if not coordinates or len(coordinates) < 2:
        return 1
    start_lng, start_lat = coordinates[0]
    end_lng, end_lat = coordinates[-1]
    start_dist_sq = (start_lat - SEOUL_CENTER_LAT) ** 2 + (start_lng - SEOUL_CENTER_LNG) ** 2
    end_dist_sq = (end_lat - SEOUL_CENTER_LAT) ** 2 + (end_lng - SEOUL_CENTER_LNG) ** 2
    return 1 if end_dist_sq <= start_dist_sq else 2


def rank_candidates(candidates, predictions, metadata, incidents_by_road=None, departure_at=None, speeds_by_road=None):
    incidents_by_road = incidents_by_road or {}
    speeds_by_road = speeds_by_road or {}
    roads = {}
    for prediction, meta in zip(predictions, metadata, strict=True):
        if not math.isfinite(float(prediction)):
            raise ValueError("모델이 유효하지 않은 예측값을 반환했습니다.")
        # A zero previous-day count cannot support a meaningful growth ratio.
        if meta["baseline"] <= 0:
            continue
        key = road_key(meta["spot_name"])
        direction = int(meta.get("direction_code", 1))
        roads.setdefault(key, {})[direction] = (
            max(0., float(prediction)),
            meta["baseline"],
            meta.get("typical_volume", meta["baseline"]),
        )
    results = []
    for candidate in candidates:
        total = sum(s.duration_sec for s in candidate.steps)
        matched, penalty, incident_penalty, speed_penalty, predicted, typical, count = 0., 0., 0., 0., 0., 0., 0
        matched_road_names = []
        unmatched_road_names = []
        speed_road_names = []
        speed_observed_at = []
        route_incidents = {}
        coordinates = getattr(candidate, "coordinates", [])
        preferred_direction = determine_route_direction(coordinates)
        for step in candidate.steps:
            candidates_for_step = incidents_by_road.get(road_key(step.name), [])
            for incident in candidates_for_step:
                if coordinates and incident.get("longitude") is not None:
                    if not incident_matches_route(incident, coordinates):
                        continue
                route_incidents[incident["incident_id"]] = incident
            incident_penalty += step.duration_sec * sum(
                incident_penalty_multiplier(incident) * incident_time_weight(incident, departure_at, total)
                for incident in candidates_for_step
                if not coordinates or incident_matches_route(incident, coordinates)
            )
            speed = speeds_by_road.get(road_key(step.name))
            if speed and getattr(step, "distance_m", None) and speed["speed_kmh"] > 0:
                speed_road_names.append(step.name)
                speed_observed_at.append(speed["measured_at"])
                # 관측 속도가 OSRM보다 느릴 때만 추가 지연을 부과합니다.
                observed_duration = step.distance_m / (float(speed["speed_kmh"]) / 3.6)
                speed_penalty += max(0.0, observed_duration - step.duration_sec)
            dir_map = roads.get(road_key(step.name)) if step.name else None
            if not dir_map:
                if step.name:
                    unmatched_road_names.append(step.name)
                continue
            if step.name:
                matched_road_names.append(step.name)

            # 양방향 합산(Pooling) 대신 주행 방향(preferred_direction) 관측값만 선택합니다.
            if preferred_direction in dir_map:
                forecast, baseline, normal = dir_map[preferred_direction]
            else:
                # 해당 방향이 없으면 가용한 관측 방향으로 fallback (단방향 유지)
                forecast, baseline, normal = next(iter(dir_map.values()))

            growth = min(2., max(0., forecast / baseline - 1.))
            matched += step.duration_sec
            penalty += step.duration_sec * growth
            predicted += forecast * step.duration_sec
            typical += normal * step.duration_sec
            count += 1
        coverage = matched / total if total else 0.
        traffic_penalty_ratio = penalty / total if total else 0.
        incident_rows = list(route_incidents.values())
        results.append({"id": candidate.id, "coverage": round(coverage, 3),
                        "score": round(candidate.duration_sec + penalty + incident_penalty + speed_penalty, 2) if total else candidate.duration_sec,
                        "base_duration_sec": round(candidate.duration_sec, 2),
                        "traffic_penalty_sec": round(candidate.duration_sec * traffic_penalty_ratio, 2),
                        "traffic_penalty_percent": round(traffic_penalty_ratio * 100, 1),
                        "incident_penalty_sec": round(incident_penalty, 2),
                        "speed_penalty_sec": round(speed_penalty, 2),
                        "speed_matched_road_names": list(dict.fromkeys(speed_road_names)),
                        "speed_match_ratio": round(len(set(speed_road_names)) / len(candidate.steps), 3) if candidate.steps else 0,
                        "speed_observed_at": max(speed_observed_at).isoformat() if speed_observed_at else None,
                        "incident_count": len(incident_rows),
                        "incidents": [{
                            "incident_id": incident["incident_id"],
                            "type": incident["incident_type"],
                            "category": incident_category(incident),
                            "detail_type": incident["incident_detail_type"],
                            "description": incident["description"],
                            "impact_radius_m": incident_impact_radius_m(incident),
                        } for incident in incident_rows],
                        "predicted_volume": round(predicted / matched, 1) if matched else None,
                        "typical_volume": round(typical / matched, 1) if matched else None,
                        "predicted_vs_typical_percent": round((predicted / typical - 1) * 100, 1) if typical > 0 else None,
                        "distance_m": round(candidate.distance_m, 1) if getattr(candidate, "distance_m", None) is not None else None,
                        "matched_steps": count,
                        "matched_road_names": list(dict.fromkeys(matched_road_names)),
                        "unmatched_road_names": list(dict.fromkeys(unmatched_road_names)),
                        "match_ratio": round(count / len(candidate.steps), 3) if candidate.steps else 0,
                        "ai": False})
    # Incomplete candidates must not win simply because they have no penalty.
    # A low-coverage alternative should not, however, suppress a different
    # candidate whose own coverage is sufficient for model-based ranking.
    eligible = [r for r in results if r["coverage"] >= .5]
    available = bool(eligible)
    if available:
        min(eligible, key=lambda r: r["score"])["ai"] = True
    return results, available


def incident_time_weight(incident, departure_at, route_duration_sec):
    if departure_at is None or not incident.get("expected_clear_at"):
        return 1.0
    remaining = (incident["expected_clear_at"] - departure_at).total_seconds()
    return max(0.0, min(1.0, remaining / max(1.0, route_duration_sec)))


def load_latest_road_speeds(db, target):
    # 최근 3시간의 도로별 최신 관측만 추천 비용에 사용합니다.
    rows = db.execute(text("""
        SELECT r.road_name, v.measured_at, v.speed_kmh, v.travel_time_sec
        FROM traffic_speed_measurements v
        JOIN road_segments r ON r.link_id = v.link_id
        WHERE v.measured_at <= :target
          AND v.measured_at >= :start
          AND v.speed_kmh > 0
        ORDER BY v.measured_at DESC
    """), {"target": target, "start": target - timedelta(hours=3)}).mappings()
    latest = {}
    for row in rows:
        key = road_key(row["road_name"]) if row.get("road_name") else ""
        if key and key not in latest:
            latest[key] = dict(row)
    return latest


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
    """).bindparams(bindparam("spot_ids", expanding=True)), {"spot_ids": spot_ids, "start": target-timedelta(days=30), "target": target}).mappings())
    weather = db.execute(text("""
        SELECT temperature_c, rainfall_mm, humidity_pct, wind_speed_ms, pressure_hpa, observed_at
        FROM weather_measurements WHERE weather_station_id='108'
        AND observed_at <= :now AND observed_at >= :start
        ORDER BY observed_at DESC LIMIT 1
    """), {"now": target, "start": target-timedelta(hours=36)}).mappings().first()
    if not history:
        raise ValueError("최근 교통량 관측값이 없습니다. 수집 데이터를 갱신해 주세요.")
    observed = max(row["measured_at"] for row in history)
    # Measurements are hour buckets, so compare them with the current hour
    # rather than treating the minutes elapsed within that hour as data lag.
    observation_hour = observation_clock.replace(minute=0, second=0, microsecond=0)
    if observation_hour - observed > timedelta(hours=3):
        raise ValueError("교통량 관측이 3시간 이상 지연되어 AI 추천을 보류했습니다. 수집 데이터를 갱신해 주세요.")
    # VolInfo is published about two hours late. Recursively predict missing
    # hours with the same trained model, instead of pretending old lags are current.
    records = [dict(row) for row in history]
    forecast_target = observed + timedelta(hours=1)
    columns = report["feature_columns"]
    needs_speed = any(column in columns for column in ("speed_lag_1h", "travel_time_lag_1h"))
    speed_history = []
    if needs_speed:
        speed_history = list(db.execute(text("""
            SELECT m.spot_id, v.measured_at, v.speed_kmh, v.travel_time_sec
            FROM traffic_spot_road_maps m
            JOIN traffic_speed_measurements v ON v.link_id = m.link_id
            WHERE m.is_primary = TRUE AND v.measured_at >= :start AND v.measured_at <= :target
            ORDER BY m.spot_id, v.measured_at
        """), {"start": target - timedelta(days=30), "target": target}).mappings())
    forecast_steps = 0
    while forecast_target <= target:
        features, metadata = build_features(records, weather, forecast_target, speed_history)
        if set(columns) - set(features.columns):
            raise ValueError("학습 모델의 입력 특성과 현재 추론 특성이 다릅니다.")
        predictions = np.asarray(model.predict(features[columns]), dtype=float)
        if not np.isfinite(predictions).all():
            raise ValueError("모델이 유효하지 않은 예측값을 반환했습니다.")
        for value, meta in zip(predictions, metadata, strict=True):
            records.append({**meta, "measured_at": forecast_target, "volume": max(0., float(value))})
        forecast_target += timedelta(hours=1)
        forecast_steps += 1
    incidents_by_road = load_active_incidents(db, target)
    speeds_by_road = load_latest_road_speeds(db, target)
    results, available = rank_candidates(
        candidates, predictions, metadata, incidents_by_road, target_clock, speeds_by_road
    )
    eligible_count = sum(route["coverage"] >= .5 for route in results)
    selected = next((route for route in results if route["ai"]), None)
    osrm_default = min(results, key=lambda route: route["base_duration_sec"])
    comparable_to_osrm = bool(selected and osrm_default["coverage"] >= .5)
    saved_seconds = max(0., osrm_default["score"] - selected["score"]) if comparable_to_osrm else None
    extra_distance = None
    if comparable_to_osrm and selected["distance_m"] is not None and osrm_default["distance_m"] is not None:
        extra_distance = selected["distance_m"] - osrm_default["distance_m"]
    return {"model_version": report["model_version"], "algorithm": report["algorithm"],
            "rmse": float(report["rmse"]), "target_at": target.isoformat()+"+09:00",
            "available": available, "routes": results,
            "observed_at": observed.isoformat()+"+09:00",
            "weather_at": weather["observed_at"].isoformat()+"+09:00", "forecast_steps": forecast_steps,
            "target_context": {
                "weekday": ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][target.weekday()],
                "hour": target.hour,
                "temperature_c": float(weather["temperature_c"]),
                "rainfall_mm": float(weather["rainfall_mm"] or 0),
                "humidity_pct": float(weather["humidity_pct"]),
            },
            "osrm_comparison": {
                "osrm_default_route_id": osrm_default["id"],
                "ai_selected_route_id": selected["id"] if selected else None,
                "estimated_minutes_saved": round(saved_seconds / 60, 1) if saved_seconds is not None else None,
                "extra_distance_km": round(extra_distance / 1000, 2) if extra_distance is not None else None,
                "basis": "traffic_adjusted_comparison_score",
            },
            "message": f"베스트 모델 교통량 예측 반영 · 후보 {eligible_count}/{len(results)}개 평가 · 실시간 관측과 최근 30일 시간대 패턴 사용 · {forecast_steps}시간 순차 예측 · 기상 {weather['observed_at']:%m/%d %H시} 관측 유지 · 도로명·진행 방향 기준 교통량 매칭 · 소요시간은 OSRM 추정치" if available
            else "예측 반영 범위가 50% 이상인 경로 후보가 없어 AI 추천을 보류했습니다."}


def predict_spot_series(db, spot_id, now, horizon_hours=3):
    """Predict one traffic observation spot on demand for the prediction UI."""
    model, report = best_saved_model()
    target = now.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    spot = db.execute(text("""
        SELECT spot_id, spot_name, tm_x, tm_y FROM traffic_spots WHERE spot_id=:spot_id
    """), {"spot_id": spot_id}).mappings().first()
    if not spot:
        raise ValueError("선택한 도로 측정지점을 찾을 수 없습니다.")
    history = list(db.execute(text("""
        SELECT v.spot_id, s.spot_name, s.tm_x, s.tm_y, v.direction_code,
               v.measured_at, SUM(v.traffic_volume) AS volume
        FROM traffic_volume_measurements v JOIN traffic_spots s ON s.spot_id=v.spot_id
        WHERE v.spot_id=:spot_id AND v.measured_at>=:start AND v.measured_at<:target
        GROUP BY v.spot_id, s.spot_name, s.tm_x, s.tm_y, v.direction_code, v.measured_at
        ORDER BY v.measured_at
    """), {"spot_id": spot_id, "start": target-timedelta(days=30), "target": target}).mappings())
    weather = db.execute(text("""
        SELECT temperature_c, rainfall_mm, humidity_pct, wind_speed_ms, pressure_hpa, observed_at
        FROM weather_measurements WHERE weather_station_id='108'
        AND observed_at<=:now AND observed_at>=:start
        ORDER BY observed_at DESC LIMIT 1
    """), {"now": target, "start": target-timedelta(hours=36)}).mappings().first()
    if not history:
        raise ValueError("선택한 도로의 최근 교통량이 없습니다.")
    observed = max(row["measured_at"] for row in history)
    if target - observed > timedelta(hours=3):
        raise ValueError("선택한 도로의 실시간 교통량이 3시간 이상 지연됐습니다.")

    records = [dict(row) for row in history]
    forecast_target = observed + timedelta(hours=1)
    end = target + timedelta(hours=horizon_hours)
    columns = report["feature_columns"]
    points = []
    while forecast_target <= end:
        features, metadata = build_features(records, weather, forecast_target)
        predictions = np.asarray(model.predict(features[columns]), dtype=float)
        if not np.isfinite(predictions).all():
            raise ValueError("모델이 유효하지 않은 예측값을 반환했습니다.")
        for value, meta in zip(predictions, metadata, strict=True):
            records.append({**meta, "measured_at": forecast_target, "volume": max(0., float(value))})
        if forecast_target >= target:
            points.append({
                "target_at": forecast_target.isoformat()+"+09:00",
                "predicted_volume": round(sum(max(0., float(value)) for value in predictions), 1),
            })
        forecast_target += timedelta(hours=1)
    current = sum(float(row["volume"]) for row in history if row["measured_at"] == observed)
    return {
        "spot_id": spot["spot_id"], "road": spot["spot_name"],
        "observed_at": observed.isoformat()+"+09:00", "current_volume": round(current, 1),
        "model_version": report["model_version"], "algorithm": report["algorithm"],
        "points": points,
    }
