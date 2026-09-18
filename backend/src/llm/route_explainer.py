"""Grounded LLM explanation layer for model-ranked routes."""

from typing import Any

from backend.src.llm.client import LLMError, NvidiaLLMClient
from backend.src.llm.prompts import (
    ROUTE_EXPLANATION_SYSTEM_PROMPT,
    build_route_evidence,
    route_explanation_user_prompt,
)


def _template_explanation(evidence: dict[str, Any]) -> str:
    selected_id = evidence.get("selected_route_id", "A")
    routes = evidence.get("routes", [])
    selected = next((route for route in routes if route["route_id"] == selected_id), {})
    roads = "·".join(selected.get("main_roads", [])[:2]) or f"경로 {selected_id} 주요 도로"
    time_min = selected.get("predicted_duration_minutes") or round(selected.get("comparison_score", 0) / 60)

    comparison_data = evidence.get("osrm_comparison") or {}
    saved = comparison_data.get("estimated_minutes_saved")

    if saved is not None and saved > 0:
        point1 = f"대안 경로 대비 예상 정체 구간이 적어 약 {saved:g}분 더 빠르게 도착할 수 있어요."
    else:
        point1 = f"비교 후보 경로 중 예상 정체 지연이 가장 적어 최단 시간({time_min}분)에 도착할 수 있어요."

    now_min = selected.get("now_duration_minutes")
    if now_min is not None and now_min > 0:
        if now_min > time_min:
            point1 = f"지금 출발하면 {now_min}분 걸리지만, 선택하신 시간에 출발하면 도로 상황이 원활해져서 {time_min}분 걸려요."
        elif now_min < time_min:
            point1 = f"지금 출발하면 {now_min}분 걸리지만, 선택하신 시간에 출발하면 도로 상황이 혼잡해져서 {time_min}분 걸려요."
        else:
            point1 = f"지금 출발하셔도 {now_min}분으로 소요시간이 동일하게 예상됩니다."

    incident_count = selected.get("incident_count", 0)
    if incident_count > 0:
        point2 = f"{roads} 구간을 경유하며, 경로 내 돌발 상황({incident_count}건)을 효과적으로 우회하도록 안내해요."
    else:
        point2 = f"{roads} 구간의 실시간 통행 흐름이 원활하며 돌발(사고·공사) 지연이 없어요."

    point3 = "시간대별 교통량 패턴과 실시간 주행 데이터를 종합 분석한 최적 경로예요."

    return f"1. {point1}\n2. {point2}\n3. {point3}"


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
            "text": recommendation.get("message", "설명할 최적 추천 경로가 없습니다."),
            "source": "system",
            "llm_model": None,
        }

    llm = client or NvidiaLLMClient()
    try:
        raw_text = llm.complete(
            system=ROUTE_EXPLANATION_SYSTEM_PROMPT,
            user=route_explanation_user_prompt(evidence),
        )
        
        # Try parsing as JSON first
        text = raw_text
        try:
            import json
            import re
            match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if match:
                reasons = json.loads(match.group(0))
                if isinstance(reasons, list) and len(reasons) >= 3:
                    text = f"1. {reasons[0]}\n2. {reasons[1]}\n3. {reasons[2]}"
        except Exception:
            pass

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
