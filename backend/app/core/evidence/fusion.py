"""Reciprocal rank fusion (Cormack, Clarke and Buettcher 2009) of file rankings, as decision 0012
fixes it: each retriever ranks files (each with its best passage), the first `POOL` of each count,
a file scores the sum of 1 / (k + rank) and keeps the passage of the ranking that put it highest.
Ties keep the order of first appearance (an earlier ranking first)."""

from collections.abc import Sequence

RRF_K = 5  # rag's v3 eval (decision 0012): k=5 26 of 30 in the first 5 against k=60's 23
POOL = 50  # files each retriever gives to the fusion

FileRanking = Sequence[tuple[str, str]]  # (file id, its best passage id), best first


def fused(
    rankings: Sequence[FileRanking], k: int = RRF_K, pool: int = POOL
) -> list[tuple[str, str, float]]:
    """(file id, passage id, fused score), best first."""
    scores: dict[str, float] = {}
    best: dict[str, tuple[int, str]] = {}
    for ranking in rankings:
        for rank, (file_id, passage) in enumerate(ranking[:pool], start=1):
            scores[file_id] = scores.get(file_id, 0.0) + 1.0 / (k + rank)
            if file_id not in best or rank < best[file_id][0]:
                best[file_id] = (rank, passage)
    order = sorted(scores, key=lambda file_id: -scores[file_id])
    return [(file_id, best[file_id][1], scores[file_id]) for file_id in order]
