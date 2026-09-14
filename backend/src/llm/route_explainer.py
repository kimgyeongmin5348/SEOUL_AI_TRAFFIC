"""Grounded LLM explanation layer for model-ranked routes."""

from typing import Any

from backend.src.llm.client import LLMError, NvidiaLLMClient
from backend.src.llm.prompts import (
    ROUTE_EXPLANATION_SYSTEM_PROMPT,
    build_route_evidence,
    route_explanation_user_prompt,
)


def _template_explanation(evidence: dict[str, Any]) -> str:
    selected_id = evidence["selected_route_id"]
    selected = next(route for route in evidence["routes"] if route["route_id"] == selected_id)
    others = sorted(
        (route for route in evidence["routes"] if route["route_id"] != selected_id),
        key=lambda route: route["comparison_score"],
    )
    roads = "·".join(selected["main_roads"][:2]) or f"경로 {selected_id}"
    comparison = "비교 가능한 후보 중 혼잡 반영 점수가 가장 낮습니다."
    if others and others[0]["comparison_score"]:
        gap = max(0, round((others[0]["comparison_score"] - selected["comparison_score"]) / others[0]["comparison_score"] * 100))
        comparison = f"다음 후보보다 혼잡 반영 비교 점수가 약 {gap}% 낮습니다."
    volume = selected["predicted_hourly_volume"]
    volume_text = f" 시간당 평균 교통량은 약 {round(volume):,}대로 예측됐고," if volume is not None else ""
    comparison_data = evidence.get("osrm_comparison") or {}
    saved = comparison_data.get("estimated_minutes_saved")
    extra_distance = comparison_data.get("extra_distance_km")
    saving_text = ""
    if saved is not None:
        distance_text = f" 거리는 약 {extra_distance:g}km 더 길지만" if extra_distance is not None and extra_distance > 0 else ""
        saving_text = f"{distance_text} 교통량 반영 추정치로 OSRM 기본 경로보다 약 {saved:g}분 단축됩니다. "
    return (
        f"교통량 예측 AI는 {roads}를 포함한 경로 {selected_id}를 추천했습니다.{volume_text} "
        f"예측 교통 증가 페널티는 약 {selected['predicted_traffic_penalty_minutes']}분이고 "
        f"실제 관측 도로 연결 범위는 {selected['prediction_coverage_percent']}%입니다. {saving_text}{comparison} "
        "비교 점수는 실제 예상 도착시간이 아닙니다."
    )


def explain_route_recommendation(
    recommendation: dict[str, Any],
    candidates: list[Any],
    *,
    client: NvidiaLLMClient | None = None,
) -> dict[str, Any]:
    """Generate an explanation without allowing LLM failure to break ranking."""
    evidence = build_route_evidence(recommendation, candidates)
    if evidence is None:
        return {
            "selected_route_id": None,
            "text": recommendation.get("message", "설명할 AI 추천 경로가 없습니다."),
            "source": "system",
            "llm_model": None,
        }

    llm = client or NvidiaLLMClient()
    try:
        text = llm.complete(
            system=ROUTE_EXPLANATION_SYSTEM_PROMPT,
            user=route_explanation_user_prompt(evidence),
        )
        return {
            "selected_route_id": evidence["selected_route_id"],
            "text": text,
            "source": "llm",
            "llm_model": llm.model,
        }
    except LLMError:
        return {
            "selected_route_id": evidence["selected_route_id"],
            "text": _template_explanation(evidence),
            "source": "template",
            "llm_model": None,
        }
