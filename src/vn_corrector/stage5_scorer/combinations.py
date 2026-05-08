"""Generate candidate sequences from a window."""

from __future__ import annotations

import itertools
from itertools import islice

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
        # Invariant: position 0 is always the original token;
        # positions 1..N are alternatives sorted by descending prior_score.
        original_texts = [c.text for c in tc.candidates if c.text == tc.token_text][:1]
        alternatives = sorted(
            [c for c in tc.candidates if c.text != tc.token_text],
            key=lambda c: c.prior_score,
            reverse=True,
        )
        texts = original_texts + [c.text for c in alternatives]
        candidate_lists.append(texts[:max_per_token])

    total = 1
    for cl in candidate_lists:
        total *= len(cl)

    if total > max_combinations:
        # Only count positions with multiple candidates for the root
        # calculation.  Positions with 1 candidate (e.g. spaces) contribute
        # factor 1 and should not reduce the effective per-position cap.
        multi_positions = sum(1 for cl in candidate_lists if len(cl) > 1)
        if multi_positions > 0:
            max_per_pos = max(2, int(max_combinations ** (1.0 / multi_positions)))
        else:
            max_per_pos = 2
        candidate_lists = [cl[:1] + cl[1:max_per_pos] for cl in candidate_lists]

    results: list[CandidateSequence] = []
    for combo in islice(itertools.product(*candidate_lists), max_combinations):
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
