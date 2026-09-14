from backend.src.llm.chatbot import get_traffic_chat_reply
from backend.src.llm.client import LLMError


class StubChatClient:
    model = "test-thinking-model"

    def complete_chat(self, *, system, messages, max_tokens=2048):
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
    res = get_traffic_chat_reply([{"role": "user", "content": "강남대로 상황 어때?"}], client=client)
    assert res["reply"] == "강남대로는 현재 통행량이 많아 서행 중입니다."
    assert "Analyzing" in res["thinking"]
    assert res["model"] == "test-thinking-model"


def test_chatbot_gracefully_handles_failure():
    client = FailingChatClient()
    res = get_traffic_chat_reply([{"role": "user", "content": "강남대로 상황 어때?"}], client=client)
    assert "일시적인 지연" in res["reply"]
    assert res["thinking"] is None
