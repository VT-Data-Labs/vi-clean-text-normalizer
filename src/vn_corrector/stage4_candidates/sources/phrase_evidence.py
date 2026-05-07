"""Phrase-evidence source — tags candidates with phrase context evidence.

Inspects local token windows up to ``max_phrase_window`` and,
if the candidate forms a known phrase, adds PHRASE_SPECIFIC evidence.
"""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.common.lexicon import LexiconStoreInterface
from vn_corrector.stage1_normalize import normalize_key
from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


class PhraseEvidenceSource(CandidateSourceGenerator):
    """Tag existing candidates with phrase-context evidence.

    This source does **not** generate new candidate texts. Instead it
    inspects local windows around the target token and, when a candidate
    text forms a known phrase in the lexicon, yields a
    ``PHRASE_SPECIFIC`` proposal that can be merged into the existing
    candidate.
    """

    source = CandidateSource.PHRASE_SPECIFIC

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        tokens = context.tokens
        if tokens is None or request.token_index is None:
            return

        config = context.config
        max_window = config.max_phrase_window
        lexicon = context.lexicon
        prior_weight = config.source_prior_weights.get(CandidateSource.PHRASE_SPECIFIC, 0.35)

        idx = request.token_index
        token_count = len(tokens)

        # Collect all candidate texts for this token (from the generator)
        candidate_texts = context.candidate_texts or {request.token_text}

        for candidate_text in candidate_texts:
            # Check local windows: [idx-w, idx+w] for w in 1..max_window
            found_match = False
            matched_phrase = None
            for window_size in range(1, max_window + 1):
                start = max(0, idx - window_size + 1)
                end = min(token_count, idx + window_size)

                if end - start < 2:
                    continue  # need at least 2 tokens for a phrase

                # Build the candidate-substituted window
                window_tokens = []
                for i in range(start, end):
                    if i == idx:
                        window_tokens.append(candidate_text)
                    else:
                        window_tokens.append(tokens[i].text)

                window_phrase = " ".join(window_tokens)
                window_key = normalize_key(window_phrase)

                if _phrase_exists(lexicon, window_key, window_phrase):
                    found_match = True
                    matched_phrase = window_phrase
                    break

            if found_match and matched_phrase:
                yield CandidateProposal(
                    text=candidate_text,
                    source=CandidateSource.PHRASE_SPECIFIC,
                    evidence=CandidateEvidence(
                        source=CandidateSource.PHRASE_SPECIFIC,
                        detail=f"phrase_match: {matched_phrase}",
                        matched_text=matched_phrase,
                        matched_key=normalize_key(matched_phrase),
                        metadata={
                            "window_start": max(0, idx - (len(matched_phrase.split()) - 1)),
                            "window_end": min(token_count, idx + (len(matched_phrase.split()) - 1)),
                        },
                    ),
                    prior_score=prior_weight,
                )


def _phrase_exists(lexicon: LexiconStoreInterface, normalized_key: str, raw_phrase: str) -> bool:
    """Check if *raw_phrase* is a known phrase in the lexicon."""
    try:
        result = lexicon.lookup_phrase_str(raw_phrase)
        if result is not None:
            return True
    except (AttributeError, TypeError):
        pass

    try:
        entries = lexicon.lookup_phrase(raw_phrase)
        if entries and len(entries) > 0:
            return True
    except (AttributeError, TypeError):
        pass

    try:
        phrase_entries = lexicon.lookup_phrase_normalized(normalized_key)
        if phrase_entries and len(phrase_entries) > 0:
            return True
    except (AttributeError, TypeError):
        pass

    return False


__all__ = ["PhraseEvidenceSource"]
