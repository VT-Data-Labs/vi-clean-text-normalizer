"""Deterministic candidate ranking for Stage 4.

Uses a lightweight prior score to order candidates within a token.
This is **not** the final correction score (M5/M6 handles that).
"""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import Candidate

# Prior-scoring weight constants
KNOWN_WORD_BONUS = 0.05
SYLLABLE_FREQ_WEIGHT = 0.3
WORD_FREQ_WEIGHT = 0.15
ORIGINAL_BONUS = 0.05
EVIDENCE_WEIGHT = 0.02
EVIDENCE_CAP = 5


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

    # Known-word bonus
    if candidate.is_known_word:
        score += KNOWN_WORD_BONUS

    # Syllable frequency bonus
    if candidate.syllable_freq is not None:
        score += candidate.syllable_freq * SYLLABLE_FREQ_WEIGHT

    # Word frequency bonus
    if candidate.word_freq is not None:
        score += candidate.word_freq * WORD_FREQ_WEIGHT

    # Original bonus
    if candidate.is_original:
        score += ORIGINAL_BONUS

    # Evidence count bonus (capped)
    score += min(len(candidate.evidence), EVIDENCE_CAP) * EVIDENCE_WEIGHT

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
) -> tuple[float, float, float, int, int]:
    score, candidate = item
    return (
        score,
        candidate.word_freq or 0.0,
        candidate.syllable_freq or 0.0,
        len(candidate.evidence),
        -(candidate.edit_distance or 999),
    )


__all__ = ["compute_prior_score", "rank_candidates"]
