"""Deterministic candidate ranking for Stage 4.

Uses a lightweight prior score to order candidates within a token.
This is **not** the final correction score (M5/M6 handles that).
"""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import Candidate


def compute_prior_score(
    candidate: Candidate,
    source_prior_weights: dict[str, float],
) -> float:
    """Compute a lightweight prior score for ordering candidates within a token."""
    score = 0.0

    # Best source weight
    best_weight = 0.0
    for src in candidate.sources:
        w = source_prior_weights.get(str(src), 0.0)
        if w > best_weight:
            best_weight = w
    score += best_weight

    # Frequency bonus
    score += candidate.lexicon_freq * 0.3

    # Original bonus
    if candidate.is_original:
        score += 0.05

    # Evidence count bonus (more evidence = more reliable)
    score += len(candidate.evidence) * 0.02

    return max(0.0, min(1.0, score))


def rank_candidates(
    candidates: list[Candidate],
    source_prior_weights: dict[str, float],
    keep_original_first: bool = False,
) -> list[Candidate]:
    """Rank candidates by prior score, optionally keeping the original first."""
    scored = [(compute_prior_score(c, source_prior_weights), c) for c in candidates]
    scored.sort(key=_sort_key, reverse=True)
    result = [c for _, c in scored]

    if keep_original_first and result:
        orig_idx = next(
            (i for i, c in enumerate(result) if c.is_original),
            None,
        )
        if orig_idx is not None and orig_idx > 0:
            result.insert(0, result.pop(orig_idx))

    return result


def _sort_key(
    item: tuple[float, Candidate],
) -> tuple[float, int, str]:
    score, candidate = item
    return (score, 1 if candidate.is_original else 0, candidate.text)


__all__ = ["compute_prior_score", "rank_candidates"]
