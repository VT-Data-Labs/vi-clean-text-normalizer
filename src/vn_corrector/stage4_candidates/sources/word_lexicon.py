"""Word-lexicon source — adds WORD_LEXICON evidence to known dictionary words."""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.lexicon.types import LexiconEntry
from vn_corrector.stage1_normalize import to_no_tone_key
from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


class WordLexiconSource(CandidateSourceGenerator):
    """Generate WORD_LEXICON candidates from the word/unit lexicon.

    This source does two things:
    1. Generates known-word candidates from the no-tone key.
    2. Assigns WORD_LEXICON evidence to surface forms that are known
       dictionary words (regardless of whether they were also generated
       by syllable map or OCR confusion).
    """

    source = CandidateSource.WORD_LEXICON

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        lexicon = context.lexicon
        prior_weight = context.config.source_prior_weights.get(CandidateSource.WORD_LEXICON, 0.25)
        no_tone = to_no_tone_key(request.token_text)

        # Try lookup_accentless which returns both syllable and word entries
        try:
            result = lexicon.lookup_accentless(no_tone)
            if result is not None:
                entries = [e for e in result.entries if isinstance(e, (LexiconEntry,))]
            else:
                entries = []
        except (AttributeError, TypeError):
            return

        for entry in entries:
            kind = getattr(entry, "kind", None)
            kind_str = str(kind) if kind is not None else getattr(entry, "type", "unknown")
            if kind_str not in ("word", "unit", "name", "location", "brand"):
                continue

            if entry.surface == request.token_text:
                continue

            freq = getattr(entry, "score", None)
            freq_val = freq.frequency if freq is not None else 0.0
            yield CandidateProposal(
                text=entry.surface,
                source=CandidateSource.WORD_LEXICON,
                evidence=CandidateEvidence(
                    source=CandidateSource.WORD_LEXICON,
                    detail=f"known_word: {entry.surface} (kind={kind_str})",
                    matched_key=no_tone,
                    metadata={
                        "surface": entry.surface,
                        "kind": kind_str,
                        "frequency": freq_val,
                    },
                ),
                prior_score=prior_weight + freq_val * 0.3,
            )


__all__ = ["WordLexiconSource"]
