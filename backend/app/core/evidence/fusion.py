"""Reciprocal rank fusion (Cormack, Clarke and Buettcher 2009): each retriever's ranked ids, fused
by the sum of 1 / (k + rank). Ties keep the order of first appearance."""

from collections.abc import Sequence

RRF_K = 60


def fused(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Ids with their fused score, best first. A ranking is a list of ids, best first (rank 1)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, found in enumerate(ranking, start=1):
            scores[found] = scores.get(found, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: -item[1])
