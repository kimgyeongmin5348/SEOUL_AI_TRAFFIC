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


def _model_eta_explanation(evidence: dict[str, Any], selected: dict[str, Any]) -> str:
    selected_id = selected["route_id"]
    roads = "·".join(selected["main_roads"][:2]) or f"경로 {selected_id}"
    quality = selected.get("eta_quality") or {}
    coverage = quality.get("speed_lag_coverage")
    age = quality.get("speed_lag_age_min")
    incidents = quality.get("active_incident_count") or 0
    basis = f" 속도 관측 반영 비율은 {round(coverage * 100)}%" if coverage is not None else ""
    basis += f", 관측은 {round(age)}분 전 값" if age is not None else ""
    basis += f"이고 경로 위 활성 돌발은 {incidents}건입니다." if basis else f"경로 위 활성 돌발은 {incidents}건입니다."
    others = sorted((r for r in evidence["routes"] if r["route_id"] != selected_id and r.get("predicted_eta_minutes") is not None),
                    key=lambda r: r["predicted_eta_minutes"])
    # 화면이 문장 단위로 나눠 보여주므로 소수점 없이 정수 분으로 씁니다.
    eta = round(selected["predicted_eta_minutes"])
    base = round(selected["base_duration_minutes"]) if selected.get("base_duration_minutes") is not None else None
    comparison = ""
    if others:
        gap = max(0, round(others[0]["predicted_eta_minutes"] - selected["predicted_eta_minutes"]))
        comparison = (f" 다음 후보 {others[0]['route_id']}(약 {round(others[0]['predicted_eta_minutes'])}분)보다 {gap}분 빠릅니다."
                      if gap >= 1 else f" 다음 후보 {others[0]['route_id']}와 예측 시간이 거의 같습니다.")
    base_text = f"(OSRM 기본 {base}분)" if base is not None else ""
    return (
        f"경로 예측 AI는 {roads}를 포함한 경로 {selected_id}를 추천했습니다. "
        f"예상 소요시간은 약 {eta}분{base_text}이며,{basis}{comparison} "
        "예측값은 링크 관측 속도로 학습한 모델의 추정치이며 관측이 없는 구간은 OSRM 시간을 따릅니다."
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
                    # Filter out obvious chain of thought logic that shouldn't be here
                    is_clean = True
                    for reason in reasons:
                        if "But rule:" in reason or "So we need" in reason or "That is" in reason:
                            is_clean = False
                    
                    if is_clean:
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
