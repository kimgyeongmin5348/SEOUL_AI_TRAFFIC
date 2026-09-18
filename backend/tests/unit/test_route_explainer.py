from types import SimpleNamespace

from backend.src.llm.client import LLMError, NvidiaLLMClient
from backend.src.llm.prompts import build_route_evidence
from backend.src.llm.route_explainer import explain_route_recommendation


def candidates():
    return [
        SimpleNamespace(
            id="A", duration_sec=600,
            steps=[SimpleNamespace(name="강남대로", duration_sec=600)],
        ),
        SimpleNamespace(
            id="B", duration_sec=660,
            steps=[SimpleNamespace(name="테헤란로", duration_sec=660)],
        ),
    ]


def recommendation():
    return {
        "available": True,
        "model_version": "traffic-v1",
        "algorithm": "XGBoost",
        "rmse": 12.3,
        "target_at": "2026-09-14T18:00:00+09:00",
        "observed_at": "2026-09-14T17:00:00+09:00",
        "weather_at": "2026-09-14T17:00:00+09:00",
        "forecast_steps": 1,
        "routes": [
            {"id": "A", "coverage": 0.8, "score": 720, "traffic_penalty_sec": 120, "traffic_penalty_percent": 20, "predicted_volume": 1200, "matched_steps": 1, "ai": True},
            {"id": "B", "coverage": 0.7, "score": 800, "traffic_penalty_sec": 140, "traffic_penalty_percent": 21.2, "predicted_volume": 1500, "matched_steps": 1, "ai": False},
        ],
    }


class StubClient:
    model = "test-model"

    def complete(self, *, system, user):
        assert "경로를 새로 선택하거나" in system
        assert '"selected_route_id":"A"' in user
        return "A 경로가 유효 후보 중 비교 점수가 가장 낮아 추천됐습니다."


class FailingClient:
    model = "test-model"

    def complete(self, *, system, user):
        raise LLMError("failure")


def test_evidence_contains_ranked_facts_but_not_unavailable_features():
    evidence = build_route_evidence(recommendation(), candidates())
    assert evidence["selected_route_id"] == "A"
    assert evidence["routes"][0]["base_duration_minutes"] == 10
    assert evidence["routes"][0]["prediction_coverage_percent"] == 80
    assert evidence["routes"][0]["predicted_traffic_penalty_minutes"] == 2
    assert evidence["routes"][0]["realtime_road_state"] == {
        "average_speed_kmh": None,
        "accident_count": None,
        "construction_count": None,
        "control_count": None,
        "used_in_ranking": False,
    }
    assert "incidents" not in evidence["routes"][0]
    assert "speed" not in evidence["routes"][0]


def test_llm_explanation_is_returned_for_selected_route():
    result = explain_route_recommendation(recommendation(), candidates(), client=StubClient())
    assert result == {
        "selected_route_id": "A",
        "text": "A 경로가 유효 후보 중 비교 점수가 가장 낮아 추천됐습니다.",
        "source": "llm",
        "llm_model": "test-model",
    }


def test_llm_failure_falls_back_without_losing_recommendation():
    result = explain_route_recommendation(recommendation(), candidates(), client=FailingClient())
    assert result["selected_route_id"] == "A"
    assert result["source"] == "template"
    assert "최적 경로" in result["text"] or "도착할 수 있어요" in result["text"]


def test_client_builds_nvidia_chat_completions_url():
    client = NvidiaLLMClient(api_key="key", base_url="https://example.test/v1", model="model")
    assert client.configured
    assert client._endpoint() == "https://example.test/v1/chat/completions"
