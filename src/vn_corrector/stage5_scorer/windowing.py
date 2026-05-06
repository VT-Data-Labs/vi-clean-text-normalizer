"""Build bounded candidate windows around ambiguous tokens."""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import CandidateWindow


def build_windows(
    token_candidates: list[TokenCandidates],
    max_tokens_per_window: int = 7,
) -> list[CandidateWindow]:
    """Build windows around tokens with more than one candidate.

    For each ambiguous (non-protected, >1 candidate) token a window
    of ``radius = max_tokens_per_window // 2`` tokens on each side is
    created.  Overlapping windows are merged.  Windows are clamped to
    *max_tokens_per_window*.

    Returns an empty list when no ambiguous tokens exist.
    """
    ambiguous_indices = [
        i for i, tc in enumerate(token_candidates) if not tc.protected and len(tc.candidates) > 1
    ]
    if not ambiguous_indices:
        return []

    radius = max_tokens_per_window // 2
    total = len(token_candidates)

    raw_windows: list[tuple[int, int]] = []
    for idx in ambiguous_indices:
        start = max(0, idx - radius)
        end = min(total, idx + radius + 1)
        if end - start > max_tokens_per_window:
            end = start + max_tokens_per_window
        raw_windows.append((start, end))

    merged: list[tuple[int, int]] = []
    for start, end in sorted(raw_windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return [
        CandidateWindow(
            start=start,
            end=end,
            token_candidates=token_candidates[start:end],
        )
        for start, end in merged
    ]
