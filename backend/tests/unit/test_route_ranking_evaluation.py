"""경로 후보 순위 평가 지표 검증."""
from backend.src.services.route_ranking_evaluation import (
    evaluate_requests,
    mean_regret,
    pairwise_ranking_accuracy,
    top1_accuracy,
)


def _request(route_id, score, actual):
    return {
        "candidates": [
            {"route_id": rid, "score": s, "actual_duration_sec": a}
            for rid, s, a in zip(route_id, score, actual)
        ]
    }


def test_top1_accuracy_counts_correct_selection():
    # 점수 1위(A)가 실제 최적(A)과 일치하는 요청 1건
    requests = [_request(["A", "B"], [100, 200], [300, 400])]
    assert top1_accuracy(requests) == 1.0


def test_top1_accuracy_skips_single_candidate_requests():
    requests = [_request(["A"], [100], [300])]
    assert top1_accuracy(requests) is None


def test_pairwise_accuracy_partial():
    # (A,B): 점수 A<B, 실제 A<B → 일치. (A,C): 점수 A<C, 실제 A<C → 일치.
    # (B,C): 점수 B<C, 실제 B>C → 불일치. 3쌍 중 2 일치.
    requests = [_request(["A", "B", "C"], [100, 200, 300], [300, 500, 400])]
    assert pairwise_ranking_accuracy(requests) == 2 / 3


def test_mean_regret_positive_difference_only():
    # 추천 A(실제 300), 최적 B(실제 250) → regret 50
    requests = [_request(["A", "B"], [100, 200], [300, 250])]
    assert mean_regret(requests) == 50.0


def test_mean_regret_zero_when_correct():
    requests = [_request(["A", "B"], [100, 200], [250, 300])]
    assert mean_regret(requests) == 0.0


def test_evaluate_requests_returns_all_metrics():
    requests = [
        _request(["A", "B"], [100, 200], [300, 400]),
        _request(["A", "B"], [100, 200], [400, 300]),
    ]
    result = evaluate_requests(requests)
    assert result["request_count"] == 2
    assert result["top1_accuracy"] == 0.5
    assert result["pairwise_ranking_accuracy"] == 0.5
    assert result["mean_regret_sec"] == 50.0