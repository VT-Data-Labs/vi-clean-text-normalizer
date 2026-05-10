"""Generate candidate sequences from a window.

Provides two strategies:

1. :func:`generate_sequences` — full Cartesian product enumeration (legacy
   fallback for tiny windows).
2. :func:`beam_search_sequences` — beam-search incremental sequence
   generation (production path).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from itertools import islice
from typing import Any

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

    This is a legacy fallback for tiny windows.  Production should use
    :func:`beam_search_sequences` instead.
    """
    if not window.token_candidates:
        return []

    original_tokens = tuple(tc.token_text for tc in window.token_candidates)

    candidate_lists: list[list[str]] = []
    for tc in window.token_candidates:
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


def beam_search_sequences(
    window: CandidateWindow,
    beam_size: int = 32,
    max_candidates_per_token: int = 8,
    ngram_score_fn: Callable[[str, str], float] | None = None,
) -> list[CandidateSequence]:
    """Generate candidate sequences via beam search.

    Builds sequences incrementally, keeping only the top ``beam_size``
    partial sequences at each step.  When ``ngram_score_fn`` is provided,
    bigram rewards are applied as soon as left context exists, helping
    contextually correct candidates survive pruning.

    The identity (all-original) path is always carried through the beam.
    """
    if not window.token_candidates:
        return []

    original_tokens = tuple(tc.token_text for tc in window.token_candidates)
    n = len(original_tokens)

    # Build per-position candidate lists (original + top alternatives)
    per_pos_lists = _per_pos_candidate_lists(window, max_candidates_per_token)

    # Beam: list of (tokens_tuple, score)
    beam: list[tuple[tuple[str, ...], float]] = [(tuple(), 0.0)]

    for pos in range(n):
        new_beam: list[tuple[tuple[str, ...], float]] = []
        for prefix_tokens, prefix_score in beam:
            for cand in per_pos_lists[pos]:
                new_tokens = (*prefix_tokens, cand.text)
                new_score = prefix_score + cand.prior_score
                # Apply bigram reward using the last content (non-whitespace) token
                if ngram_score_fn is not None and prefix_tokens:
                    left = _last_content_token(prefix_tokens)
                    if left is not None and cand.text.strip():
                        new_score += ngram_score_fn(left, cand.text)
                new_beam.append((new_tokens, new_score))
        # Keep top beam_size, preserving all entries tied for the last slot
        new_beam.sort(key=lambda x: x[1], reverse=True)
        beam = _stable_trim(new_beam, beam_size)

        # Ensure identity prefix (using original tokens) survives
        identity_prefix = original_tokens[: pos + 1]
        id_score = sum(
            next(
                (c.prior_score for c in per_pos_lists[i] if c.text == identity_prefix[i]),
                0.0,
            )
            for i in range(pos + 1)
        )
        if ngram_score_fn is not None and pos > 0:
            for i in range(1, pos + 1):
                left = _last_content_token(identity_prefix[:i])
                if left is not None:
                    id_score += ngram_score_fn(left, identity_prefix[i])
        if not any(tokens == identity_prefix for tokens, _ in beam):
            beam.append((identity_prefix, id_score))

    results: list[CandidateSequence] = []
    for tokens, _score in beam:
        changed = tuple(i for i in range(n) if tokens[i] != original_tokens[i])
        results.append(
            CandidateSequence(
                tokens=tokens,
                original_tokens=original_tokens,
                changed_positions=changed,
            )
        )

    return results


def _last_content_token(tokens: tuple[str, ...]) -> str | None:
    """Return the last non-whitespace token in *tokens*, or ``None``."""
    for t in reversed(tokens):
        if t.strip():
            return t
    return None


def _stable_trim(
    items: list[tuple[tuple[str, ...], float]],
    max_size: int,
) -> list[tuple[tuple[str, ...], float]]:
    """Trim *items* to at least *max_size*, keeping all entries tied for the last slot.

    When scores are equal (or nearly equal), entries tied at the cutoff
    point are all kept, allowing the beam to grow temporarily.  The beam
    is never trimmed below *max_size*.
    """
    if len(items) <= max_size:
        return items
    cutoff_score = items[max_size - 1][1]
    # Keep everything above the cutoff (strictly higher)
    result = [(t, s) for t, s in items if s > cutoff_score]
    # Add back all entries tied at the cutoff
    result.extend((t, s) for t, s in items if s == cutoff_score)
    return result


def _per_pos_candidate_lists(
    window: CandidateWindow,
    max_candidates_per_token: int = 8,
) -> list[list[Any]]:
    """Build per-position candidate lists for beam search (exposed for testing)."""
    per_pos_lists: list[list[Any]] = []
    for tc in window.token_candidates:
        alternatives = sorted(
            tc.candidates,
            key=lambda c: c.prior_score,
            reverse=True,
        )
        candidates_for_pos: list[Any] = []
        found_original = False
        for cand in alternatives:
            if cand.text == tc.token_text:
                found_original = True
            candidates_for_pos.append(cand)
            if len(candidates_for_pos) >= max_candidates_per_token and found_original:
                break
        if not found_original:
            candidates_for_pos.append(tc.candidates[0])
        per_pos_lists.append(candidates_for_pos)
    return per_pos_lists


__all__ = ["_per_pos_candidate_lists", "beam_search_sequences", "generate_sequences"]
