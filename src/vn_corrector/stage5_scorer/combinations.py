"""Generate candidate sequences from a window."""

from __future__ import annotations

import itertools

from vn_corrector.stage5_scorer.types import CandidateSequence, CandidateWindow


def generate_sequences(
    window: CandidateWindow,
    max_combinations: int = 5000,
    max_per_token: int = 8,
) -> list[CandidateSequence]:
    """Generate all candidate paths through *window*.

    The identity (all-original) path is always included.
    Never produces more than *max_combinations* sequences.
    Limits each token position to *max_per_token* candidates,
    but never drops the original candidate text.
    """
    if not window.token_candidates:
        return []

    original_tokens = tuple(tc.token_text for tc in window.token_candidates)

    candidate_lists: list[list[str]] = []
    for tc in window.token_candidates:
        texts = [c.text for c in tc.candidates]
        original = tc.token_text
        filtered = [original]
        for t in texts:
            if t != original and len(filtered) < max_per_token:
                filtered.append(t)
        candidate_lists.append(filtered)

    total = 1
    for cl in candidate_lists:
        total *= len(cl)

    if total > max_combinations:
        max_per_pos = max(2, int(max_combinations ** (1.0 / len(candidate_lists))))
        candidate_lists = [cl[:1] + cl[1:max_per_pos] for cl in candidate_lists]

    results: list[CandidateSequence] = []
    for combo in itertools.product(*candidate_lists):
        zipped = zip(combo, original_tokens, strict=False)
        changed = tuple(i for i, (t, o) in enumerate(zipped) if t != o)
        results.append(
            CandidateSequence(
                tokens=combo,
                original_tokens=original_tokens,
                changed_positions=changed,
            )
        )

    return results
