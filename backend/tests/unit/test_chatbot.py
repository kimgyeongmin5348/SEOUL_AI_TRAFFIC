from backend.src.llm.chatbot import get_traffic_chat_reply
from backend.src.llm.client import LLMError


class StubChatClient:
    model = "test-thinking-model"
    system = ""

    def complete_chat(self, *, system, messages, max_tokens=2048):
        self.system = system
        assert "RoadPulse" in system
        assert messages[0]["content"] == "강남대로 상황 어때?"
        return {
            "reply": "강남대로는 현재 통행량이 많아 서행 중입니다.",
            "thinking": "Analyzing Gangnam-daero traffic based on typical patterns...",
            "model": self.model,
        }


class FailingChatClient:
    model = "test-thinking-model"

    def complete_chat(self, *, system, messages, max_tokens=2048):
        raise LLMError("API failure")


def test_chatbot_returns_reply_and_thinking():
    client = StubChatClient()
    grounding = {
        "grounded": True,
        "queried_at": "2026-09-15T15:00:00+09:00",
        "matched_roads": ["강남대로"],
        "sources": ["RoadPulse 학습 모델 교통량 예측"],
        "warnings": [],
        "model_forecasts": [{"road": "강남대로", "predicted_volume": 1234}],
    }
    res = get_traffic_chat_reply(
        [{"role": "user", "content": "강남대로 상황 어때?"}],
        client=client,
        grounding=grounding,
    )
    assert res["reply"] == "강남대로는 현재 통행량이 많아 서행 중입니다."
    assert "Analyzing" in res["thinking"]
    assert res["model"] == "test-thinking-model"
    assert '"predicted_volume": 1234' in client.system
    assert res["grounding"]["grounded"] is True
    assert res["grounding"]["sources"] == ["RoadPulse 학습 모델 교통량 예측"]


def test_chatbot_prompt_prioritizes_historical_rain_evidence_over_current_null():
    client = StubChatClient()
    grounding = {
        "grounded": True,
        "weather": {"observed_at": "2026-09-15T13:00:00+09:00", "rainfall_mm": None},
        "historical_rain_impact": {
            "rainy_avg_volume": 812.3,
            "dry_avg_volume": 846.1,
            "average_change_pct": -4.0,
        },
        "sources": ["RoadPulse 2년치 교통량·기상 관측 이력"],
        "warnings": [],
    }
    get_traffic_chat_reply(
        [{"role": "user", "content": "강남대로 상황 어때?"}],
        client=client,
        grounding=grounding,
    )
    assert '"historical_rain_impact"' in client.system
    assert "null만 보고 과거 강수 비교 데이터가 없다고 판단하지 마세요" in client.system


def test_chatbot_gracefully_handles_failure():
    client = FailingChatClient()
    res = get_traffic_chat_reply([{"role": "user", "content": "강남대로 상황 어때?"}], client=client)
    assert "일시적인 지연" in res["reply"]
    assert res["thinking"] is None
