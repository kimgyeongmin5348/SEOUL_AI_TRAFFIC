from backend.src.services.chat_grounding import (
    _asks_historical_rain_impact,
    _matches_question,
    _normalize,
    _representative_spots,
)


def test_normalize_road_name():
    assert _normalize("올림픽대로 (잠실)") == "올림픽대로잠실"


def test_matches_explicit_road_term():
    assert _matches_question("강남대로", "지금 강남대로 상황 어때?", {"강남대로"})
    assert _matches_question("올림픽대로 김포방향", "올림픽대로 알려줘", {"올림픽대로"})
    assert not _matches_question("테헤란로", "올림픽대로 알려줘", {"올림픽대로"})


def test_matches_road_aliases_and_shorthand():
    from backend.src.services.chat_grounding import ROAD_ALIASES
    assert "올림픽대로" in ROAD_ALIASES.get("올림대로", [])
    assert "강변북로" in ROAD_ALIASES.get("강변", [])
    assert _matches_question("올림픽대로", "올림대로 현재상황 알려줘", {"올림픽대로"})
    assert _matches_question("강변북로", "강변 막혀?", {"강변북로"})


def test_detects_historical_rain_traffic_comparison_question():
    assert _asks_historical_rain_impact("비가 올 때 교통량이 평소보다 줄어들어?")
    assert _asks_historical_rain_impact("강수 여부에 따른 통행량 차이를 비교해줘")


def test_does_not_treat_current_weather_question_as_history_comparison():
    assert not _asks_historical_rain_impact("지금 비 와?")
    assert not _asks_historical_rain_impact("현재 교통 상황 어때?")


def test_representative_spots_are_deterministic_and_spread_across_ids():
    spots = [{"spot_id": f"A-{number:02d}", "spot_name": str(number)} for number in range(1, 25)]
    selected = _representative_spots(list(reversed(spots)), limit=3)
    assert [row["spot_id"] for row in selected] == ["A-01", "A-09", "A-17"]
