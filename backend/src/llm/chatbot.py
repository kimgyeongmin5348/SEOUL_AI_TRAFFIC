"""Conversational traffic assistant service for RoadPulse."""

from typing import Any

from backend.src.llm.client import LLMError, NvidiaLLMClient

CHATBOT_SYSTEM_PROMPT = """당신은 서울시 실시간 교통 및 AI 경로 예측 서비스인 'RoadPulse(로드펄스)'의 공식 AI 교통 비서입니다.
운전자와 시민들에게 친절하고 명확하며 신뢰할 수 있는 서울 교통 정보와 이동 팁을 제공하세요.

[지식 및 가이드라인]
1. 서울시 주요 도로 특성:
   - 올림픽대로 & 강변북로: 한강 남북을 가로지르는 핵심 간선도로로, 출퇴근 시간대(07:30~09:30, 18:00~20:00) 상습 정체 구간(한남대교~반포대교 부근, 동작대교~여의도 부근 등)이 발생합니다.
   - 내부순환로 & 동부/서부간선도로: 시내 주요 진출입로 결절점에서 병목 현상이 잦습니다.
   - 강남권(강남대로, 테헤란로): 대중교통 및 교차로 신호 대기 차량 집중으로 상시 혼잡도가 높습니다.
2. 날씨 및 돌발 상황:
   - 강수/강설 시 평균 주행 속도가 15~30% 감소하며, 지하차도 및 고가도로 결빙/침수 주의가 필요합니다.
   - 사고나 긴급 공사 발생 시 우회 경로를 적극 권장하세요.
3. RoadPulse 서비스 기능 안내:
   - RoadPulse는 OSRM 지도 기반 경로에 실제 서울시 교통량 예측 머신러닝 모델과 기상 데이터를 결합하여 최적의 추천 경로를 제공합니다.
   - 상단 메뉴의 '실시간 교통'에서 도로별 실시간 속도/혼잡도를 확인하고, '경로' 및 'AI 예측'에서 시간대별 예측 교통량을 조회할 수 있음을 안내하세요.
4. 답변 스타일:
   - 정중하고 친절한 어조(해요체)로 핵심을 먼저 간결하게 설명하세요.
   - 필요 시 중요한 주의사항은 글머리 기호나 굵은 글씨로 가독성 있게 정리하세요.
   - 한국어로 자연스럽게 답변하세요.
"""


def get_traffic_chat_reply(
    messages: list[dict[str, str]],
    *,
    client: NvidiaLLMClient | None = None,
) -> dict[str, Any]:
    """Process a chat conversation and return assistant reply and thinking process."""
    llm = client or NvidiaLLMClient()
    if not getattr(llm, "configured", True):
        return {
            "reply": "현재 AI 챗봇 연결 설정이 준비되지 않았습니다. 잠시 후 다시 이용해 주세요.",
            "thinking": None,
            "model": "offline",
        }

    try:
        result = llm.complete_chat(
            system=CHATBOT_SYSTEM_PROMPT,
            messages=messages,
            max_tokens=2048,
        )
        return result
    except LLMError as exc:
        return {
            "reply": "죄송합니다. 현재 교통 AI 응답 생성 중 일시적인 지연이 발생했습니다. 질문을 다시 보내주시거나 잠시 후 시도해 주세요.",
            "thinking": None,
            "model": llm.model or "unknown",
            "error": str(exc),
        }
