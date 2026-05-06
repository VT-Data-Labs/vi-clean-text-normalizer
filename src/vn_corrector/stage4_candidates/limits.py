"""Limit enforcement helpers for Stage 4 — Candidate Generation.

Provides functions to estimate candidate combination counts,
safely trim candidate lists, and enforce per-token limits.
"""

from __future__ import annotations

from collections.abc import Sequence

from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig
from vn_corrector.stage4_candidates.ranking import rank_candidates
from vn_corrector.stage4_candidates.types import Candidate, TokenCandidates


def estimate_combination_count(
    token_candidates: Sequence[TokenCandidates],
) -> int:
    if not token_candidates:
        return 0
    product = 1
    for tc in token_candidates:
        n = len(tc.candidates)
        if n == 0:
            return 0
        product *= n
    return product


def trim_candidate_list(
    candidates: list[Candidate],
    max_candidates: int,
    source_prior_weights: dict[str, float],
    keep_original: bool = True,
) -> list[Candidate]:
    if len(candidates) <= max_candidates:
        return list(candidates)

    ranked = rank_candidates(candidates, source_prior_weights)

    if keep_original:
        orig = next(
            (c for c in ranked if c.is_original),
            None,
        )
        if orig is not None:
            others = [c for c in ranked if not c.is_original]
            trimmed = others[: max_candidates - 1]
            result = [orig, *trimmed]
            return result

    return ranked[:max_candidates]


def trim_window_token_candidates(
    token_candidates: list[TokenCandidates],
    max_combinations: int,
    config: CandidateGeneratorConfig,
) -> list[TokenCandidates]:
    source_prior_weights = config.source_prior_weights
    keep_original = config.keep_original_first
    max_per_token = config.max_candidates_per_token

    # First enforce per-token limits
    for tc in token_candidates:
        if len(tc.candidates) > max_per_token:
            tc.candidates = trim_candidate_list(
                tc.candidates,
                max_per_token,
                source_prior_weights,
                keep_original=keep_original,
            )

    # Then trim window combinations
    while estimate_combination_count(token_candidates) > max_combinations:
        # Find the token with the most candidates (excluding original-only)
        longest_idx = -1
        longest_len = 0
        for i, tc in enumerate(token_candidates):
            if len(tc.candidates) > longest_len and len(tc.candidates) > 1:
                longest_len = len(tc.candidates)
                longest_idx = i

        if longest_idx < 0:
            break  # can't reduce further

        # Remove the last (lowest-ranked) candidate from the longest list
        trimmed = trim_candidate_list(
            token_candidates[longest_idx].candidates,
            longest_len - 1,
            source_prior_weights,
            keep_original=keep_original,
        )
        token_candidates[longest_idx].candidates = trimmed

    return token_candidates


__all__ = [
    "estimate_combination_count",
    "trim_candidate_list",
    "trim_window_token_candidates",
]
