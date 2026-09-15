from backend.src.services.chat_grounding import _matches_question, _normalize


def test_normalize_road_name():
    assert _normalize("올림픽대로 (잠실)") == "올림픽대로잠실"


def test_matches_explicit_road_term():
    assert _matches_question("강남대로", "지금 강남대로 상황 어때?", {"강남대로"})
    assert _matches_question("올림픽대로 김포방향", "올림픽대로 알려줘", {"올림픽대로"})
    assert not _matches_question("테헤란로", "올림픽대로 알려줘", {"올림픽대로"})
