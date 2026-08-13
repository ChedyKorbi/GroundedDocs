"""Reciprocal Rank Fusion (RRF).

Combines independent ranked lists into one by summing weighted
`1 / (k + rank)` contributions per document id. Ids absent from a list simply
contribute zero, which makes the fusion robust to differing recall between
rankers. Purely functional and unit-testable.
"""

from __future__ import annotations

from pydantic import BaseModel


class FusedHit(BaseModel):
    id: str
    score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None


def rrf_fuse(
    dense_hits: list[tuple[str, float]],
    sparse_hits: list[tuple[str, float]],
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    k: int = 60,
) -> list[FusedHit]:
    """Fuse (id, score) lists by weighted reciprocal rank.

    Args:
        dense_hits: dense results as (chunk_id, cosine) pairs, best first.
        sparse_hits: sparse results as (chunk_id, bm25) pairs, best first.
        dense_weight: RRF weight for the dense ranker.
        sparse_weight: RRF weight for the sparse ranker.
        k: RRF smoothing constant.

    Returns:
        Fused hits sorted by descending fused score.
    """
    dense_ranks = {cid: i for i, (cid, _) in enumerate(dense_hits, start=1)}
    sparse_ranks = {cid: i for i, (cid, _) in enumerate(sparse_hits, start=1)}
    dense_scores = dict(dense_hits)
    sparse_scores = dict(sparse_hits)

    fused: dict[str, FusedHit] = {}
    for chunk_id in dense_ranks.keys() | sparse_ranks.keys():
        score = 0.0
        if chunk_id in dense_ranks:
            score += dense_weight / (k + dense_ranks[chunk_id])
        if chunk_id in sparse_ranks:
            score += sparse_weight / (k + sparse_ranks[chunk_id])
        fused[chunk_id] = FusedHit(
            id=chunk_id,
            score=score,
            dense_rank=dense_ranks.get(chunk_id),
            sparse_rank=sparse_ranks.get(chunk_id),
            dense_score=dense_scores.get(chunk_id),
            sparse_score=sparse_scores.get(chunk_id),
        )

    return sorted(fused.values(), key=lambda hit: hit.score, reverse=True)
