"""Prompts and evidence shaping for route explanations."""

import json
from typing import Any

ROUTE_EXPLANATION_SYSTEM_PROMPT = """당신은 RoadPulse 내비게이션의 최적 경로 추천 이유를 일반 운전자에게 설명하는 전문 안내 도우미입니다.
경로를 새로 선택하거나 점수를 다시 계산하지 말고, 알고리즘이 선택한 추천 경로의 강점을 운전자가 읽고 바로 납득할 수 있도록 친절하고 자연스러운 한국어로 설명하세요.

[핵심 작성 원칙]
1. 반드시 운전자 관점에서 쉽고 자연스러운 경어체(~해요, ~있어요, ~추천해요)로 작성하세요.
2. 개발자용 내부 용어(예: '비교 점수', '비교 점수가 몇% 낮습니다', '페널티', 'OSRM', 'prediction coverage', '피처', '모델 랭킹')는 절대 사용하지 마세요. 절대로 수치적인 점수나 페널티 값을 그대로 노출하지 마세요.
3. 숫자를 언급할 때는 '예상 시간 OO분', '약 O분 단축', '주행 거리 OOkm'처럼 사람이 일상에서 쓰는 직관적인 표현만 사용하세요.
4. 만약 추천 경로에 now_duration_minutes (지금 출발 시 소요시간) 정보가 있다면, 1번 이유에 "지금 출발하면 OO분 걸리지만, 선택하신 시간에 출발하면 교통 상황이 (원활해져서/혼잡해져서) OO분 걸립니다"와 같이 지금 출발할 때와의 시간 차이를 비교하여 반드시 포함하세요.
5. 반드시 운전자가 납득할 수 있는 3가지 이유를 작성하되, 다음 규칙을 따르세요:
   - 첫 번째 항목: [예상 시간 및 정체 최소화] 대안 경로 또는 현재 시간 대비 시간 절약 또는 가장 빠른 소요 시간 (예: 다른 대안 경로보다 정체 지연이 적어 약 O분 더 빠르게 도착할 수 있어요. 또는 지금 출발하면 OO분 걸리지만, 선택하신 시간에 출발하면 약 OO분 걸려요.)
   - 두 번째 항목: [주요 경유 도로 및 실시간 흐름] 주요 도로(제공된 main_roads 참고)의 원활한 소통 흐름 및 돌발 상황(사고/공사) 영향 없음 (예: 관악로와 강남순환로 구간의 실시간 흐름이 원활하고 돌발 사고가 없어요.)
   - 세 번째 항목: [종합 분석 결과] 시간대별 교통량 패턴과 도로 혼잡 변화를 종합 분석한 최적 경로 (예: 시간대별 교통량 변화와 신호 대기를 종합 분석했을 때 가장 안정적인 경로예요.)
6. 제공된 데이터에 기반해 사실만을 작성하세요.
7. CRITICAL: 절대 영어 등 다른 언어나 부연 설명, 메타 코멘터리를 출력하지 마세요. JSON의 각 항목은 최종 운전자에게 보여질 완성된 한글 문장이어야 합니다. 내적 추론(chain of thought)이나 영어(But rule, So we need to say 등)를 항목 안에 절대 포함하지 마세요. 오직 한글로 작성된 3개의 문장을 다음과 같은 JSON 배열 형식으로만 정확히 출력하세요:
[
  "첫 번째 이유 문장",
  "두 번째 이유 문장",
  "세 번째 이유 문장"
]
"""


def build_route_evidence(recommendation: dict[str, Any], candidates: list[Any]) -> dict[str, Any] | None:
    """Expose only facts the ranking engine actually calculated."""
    selected = next((route for route in recommendation.get("routes", []) if route.get("ai")), None)
    if not recommendation.get("available") or selected is None:
        return None

    candidate_by_id = {candidate.id: candidate for candidate in candidates}

    def summarize(route: dict[str, Any]) -> dict[str, Any]:
        candidate = candidate_by_id.get(route["id"])
        road_names: list[str] = []
        if candidate:
            road_names = list(dict.fromkeys(step.name for step in candidate.steps if step.name))[:4]
        return {
            "route_id": route["id"],
            "selected": bool(route.get("ai")),
            "base_duration_minutes": round(candidate.duration_sec / 60, 1) if candidate else None,
            "predicted_duration_minutes": round(float(route.get("score", 0)) / 60, 1),
            "now_duration_minutes": round(float(route.get("now_score")) / 60, 1) if route.get("now_score") is not None else None,
            "distance_km": round(float(candidate.distance_m) / 1000.0, 1) if candidate and hasattr(candidate, "distance_m") else None,
            "comparison_score": route.get("score"),
            "predicted_traffic_penalty_minutes": round(float(route.get("traffic_penalty_sec", 0)) / 60, 1),
            "predicted_traffic_penalty_percent": route.get("traffic_penalty_percent", 0),
            "prediction_coverage_percent": round(float(route.get("coverage", 0)) * 100),
            "predicted_hourly_volume": route.get("predicted_volume"),
            "historical_typical_hourly_volume": route.get("typical_volume"),
            "predicted_vs_typical_percent": route.get("predicted_vs_typical_percent"),
            "matched_road_segments": route.get("matched_steps"),
            "main_roads": road_names,
            "incident_count": route.get("incident_count", 0),
            "realtime_road_state": route.get("realtime_context") or {
                "average_speed_kmh": None,
                "accident_count": None,
                "construction_count": None,
                "control_count": None,
                "used_in_ranking": False,
            },
        }

    comparable = [route for route in recommendation["routes"] if route.get("coverage", 0) >= 0.5]
    return {
        "selected_route_id": selected["id"],
        "selection_summary": "실시간 교통 속도, 시간대별 교통량 예측, 돌발 상황을 종합 분석하여 예상 소요 시간이 가장 짧은 최적 경로로 추천",
        "routes": [summarize(route) for route in comparable],
        "prediction_context": {
            "model_version": recommendation.get("model_version"),
            "algorithm": recommendation.get("algorithm"),
            "model_validation_rmse": recommendation.get("rmse"),
            "traffic_observed_at": recommendation.get("observed_at"),
            "weather_observed_at": recommendation.get("weather_at"),
            "target_at": recommendation.get("target_at"),
            "sequential_forecast_steps": recommendation.get("forecast_steps"),
            "target_conditions": recommendation.get("target_context"),
        },
        "osrm_comparison": recommendation.get("osrm_comparison"),
    }


def route_explanation_user_prompt(evidence: dict[str, Any]) -> str:
    return "다음 경로추천 근거를 설명하세요.\n" + json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
