"""경로 후보 순위 평가 지표를 계산합니다.

문제 정의서 §7의 경로 추천 지표를 구현합니다.
- Top-1 accuracy: 실제 최적 경로를 1순위로 선택한 비율
- Pairwise ranking accuracy: 두 후보의 실제 순서를 맞힌 비율
- Regret: 추천 경로와 실제 최적 경로의 통행시간 차이

actual_duration_sec가 재구성된 후보만 평가 대상으로 삼고, 품질 등급별로도
지표를 나눠 재구성 라벨의 한계를 숨기지 않습니다.
"""

from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.orm import Session


def top1_accuracy(requests):
    """요청별로 점수 1위 후보가 실제 통행시간 1위인지 비율을 계산합니다.

    requests: [{"candidates": [{"score", "actual_duration_sec"}, ...]}, ...]
    """
    total = 0
    correct = 0
    for request in requests:
        candidates = [c for c in request["candidates"] if c.get("actual_duration_sec") is not None]
        if len(candidates) < 2:
            continue
        total += 1
        predicted = min(candidates, key=lambda c: c["score"])
        actual = min(candidates, key=lambda c: c["actual_duration_sec"])
        if predicted is actual or predicted["route_id"] == actual["route_id"]:
            correct += 1
    return correct / total if total else None


def pairwise_ranking_accuracy(requests):
    """요청 내 모든 후보 쌍에서 점수 순서와 실제 순서가 일치하는 비율을 계산합니다."""
    total = 0
    correct = 0
    for request in requests:
        candidates = [c for c in request["candidates"] if c.get("actual_duration_sec") is not None]
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                a, b = candidates[i], candidates[j]
                if a["score"] == b["score"] or a["actual_duration_sec"] == b["actual_duration_sec"]:
                    continue
                total += 1
                predicted_order = a["score"] < b["score"]
                actual_order = a["actual_duration_sec"] < b["actual_duration_sec"]
                if predicted_order == actual_order:
                    correct += 1
    return correct / total if total else None


def mean_regret(requests):
    """추천 경로와 실제 최적 경로의 통행시간 차이(초) 평균을 계산합니다."""
    regrets = []
    for request in requests:
        candidates = [c for c in request["candidates"] if c.get("actual_duration_sec") is not None]
        if len(candidates) < 2:
            continue
        predicted = min(candidates, key=lambda c: c["score"])
        actual = min(candidates, key=lambda c: c["actual_duration_sec"])
        regrets.append(max(0.0, predicted["actual_duration_sec"] - actual["actual_duration_sec"]))
    return sum(regrets) / len(regrets) if regrets else None


def evaluate_requests(requests):
    """세 지표를 한 번에 계산해 dict로 반환합니다."""
    return {
        "request_count": sum(
            1 for r in requests
            if sum(1 for c in r["candidates"] if c.get("actual_duration_sec") is not None) >= 2
        ),
        "top1_accuracy": top1_accuracy(requests),
        "pairwise_ranking_accuracy": pairwise_ranking_accuracy(requests),
        "mean_regret_sec": mean_regret(requests),
    }


class RouteRankingEvaluationService:
    def __init__(self, db: Session):
        self.db = db

    def load_requests(self, quality: str | None = None):
        """actual_duration_sec가 채워진 후보를 요청 단위로 묶어 반환합니다."""
        query = """
            SELECT c.route_request_id, c.route_id, c.score, c.actual_duration_sec,
                   c.actual_duration_quality
            FROM route_request_candidates c
            WHERE c.actual_duration_sec IS NOT NULL
              AND c.score IS NOT NULL
        """
        params = {}
        if quality:
            query += " AND c.actual_duration_quality = :quality"
            params["quality"] = quality
        query += " ORDER BY c.route_request_id"
        rows = self.db.execute(text(query), params).mappings()
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["route_request_id"]].append({
                "route_id": row["route_id"],
                "score": float(row["score"]),
                "actual_duration_sec": float(row["actual_duration_sec"]),
                "quality": row["actual_duration_quality"],
            })
        return [{"route_request_id": key, "candidates": value} for key, value in grouped.items()]

    def evaluate(self, quality: str | None = None):
        return evaluate_requests(self.load_requests(quality))