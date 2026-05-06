"""Edit-distance fallback source — controlled approximate matching.

This source is **guarded**: it only activates when direct sources produce
few candidates. It does **not** linearly scan the full lexicon; instead it
uses the ``LexiconStore`` prefix/accentless lookups which are indexed.
"""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.common.types import AbbreviationEntry, LexiconEntry, LexiconStoreInterface
from vn_corrector.stage1_normalize import to_no_tone_key
from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between *a* and *b*."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(
                min(
                    curr[j] + 1,  # deletion
                    prev[j + 1] + 1,  # insertion
                    prev[j] + cost,  # substitution
                )
            )
        prev = curr
    return prev[-1]


class EditDistanceSource(CandidateSourceGenerator):
    """Controlled edit-distance fallback for approximate matching.

    Only activated when the token meets length constraints and there are
    few candidates. Uses the lexicon's prefix/accentless lookups rather
    than scanning the full dictionary.
    """

    source = CandidateSource.EDIT_DISTANCE

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        config = context.config
        max_dist = config.max_edit_distance
        min_len = config.min_token_length_for_edit_distance
        max_len = config.max_token_length_for_edit_distance

        token = request.token_text
        if len(token) < min_len or len(token) > max_len:
            return

        lexicon = context.lexicon
        prior_weight = config.source_prior_weights.get(CandidateSource.EDIT_DISTANCE, 0.05)

        no_tone = to_no_tone_key(token)
        candidates_found = 0

        # Try prefix search (indexed, not full scan)
        candidates = _get_prefix_candidates(lexicon, no_tone)
        for entry in candidates:
            if entry.surface == token:
                continue
            try:
                dist = _levenshtein(to_no_tone_key(entry.surface), no_tone)
            except Exception:
                continue
            if dist > max_dist or dist == 0:
                continue

            candidates_found += 1
            if candidates_found > 3:  # hard limit in fallback
                break

            freq = getattr(entry, "score", None)
            freq_val = freq.frequency if freq is not None else 0.0
            yield CandidateProposal(
                text=entry.surface,
                source=CandidateSource.EDIT_DISTANCE,
                evidence=CandidateEvidence(
                    source=CandidateSource.EDIT_DISTANCE,
                    detail=f"edit_distance={dist} on no_tone_key",
                    confidence_hint=max(0.0, 1.0 - (dist / (max_dist + 1))),
                    metadata={"distance": dist, "base_no_tone": no_tone},
                ),
                prior_score=prior_weight + freq_val * 0.1 - dist * 0.05,
                edit_distance=dist,
            )


def _get_prefix_candidates(
    lexicon: LexiconStoreInterface, no_tone: str
) -> list[LexiconEntry | AbbreviationEntry]:
    """Get candidates from lexicon via prefix lookup."""
    candidates: list[LexiconEntry | AbbreviationEntry] = []
    try:
        prefix_result = lexicon.query_prefix(no_tone)
        if prefix_result:
            candidates = list(prefix_result)
    except (AttributeError, TypeError):
        pass

    if not candidates:
        try:
            # Try first few characters as prefix
            prefix = no_tone[:3] if len(no_tone) >= 3 else no_tone
            prefix_result = lexicon.query_prefix(prefix)
            if prefix_result:
                candidates = list(prefix_result)
        except (AttributeError, TypeError):
            pass

    if not candidates:
        try:
            lookup_result = lexicon.lookup_accentless(no_tone)
            if lookup_result:
                candidates = [
                    e
                    for e in lookup_result.entries
                    if isinstance(e, (LexiconEntry, AbbreviationEntry))
                ]
        except (AttributeError, TypeError):
            pass

    return candidates


__all__ = ["EditDistanceSource"]
