"""Syllable-map source — uses no-tone key to find known accented forms."""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.common.lexicon import AbbreviationEntry, LexiconEntry, LexiconStoreInterface
from vn_corrector.stage1_normalize import to_no_tone_key
from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


class SyllableMapSource(CandidateSourceGenerator):
    """Generate candidates by looking up the no-tone key in the syllable lexicon."""

    source = CandidateSource.SYLLABLE_MAP

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        lexicon = context.lexicon
        no_tone = to_no_tone_key(request.token_text)
        prior_weight = context.config.source_prior_weights.get(CandidateSource.SYLLABLE_MAP, 0.20)

        # Prefer get_syllable_candidates for dedicated syllable lookup
        entries = _get_syllable_forms(lexicon, no_tone)
        for entry in entries:
            if entry.surface == request.token_text:
                continue
            freq = entry.score
            freq_val = freq.frequency
            yield CandidateProposal(
                text=entry.surface,
                source=CandidateSource.SYLLABLE_MAP,
                evidence=CandidateEvidence(
                    source=CandidateSource.SYLLABLE_MAP,
                    detail=f"no_tone_key={no_tone}",
                    matched_key=no_tone,
                    metadata={
                        "surface": entry.surface,
                        "frequency": freq_val,
                    },
                ),
                prior_score=prior_weight + freq_val * 0.2,
            )


def _get_syllable_forms(
    lexicon: LexiconStoreInterface, no_tone: str
) -> list[LexiconEntry | AbbreviationEntry]:
    """Get syllable entries from the lexicon matching *no_tone*."""
    try:
        return list(lexicon.get_syllable_candidates(no_tone))
    except (AttributeError, TypeError):
        pass

    try:
        result = lexicon.lookup_accentless(no_tone)
        if result is not None:
            return [e for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))]
        return []
    except (AttributeError, TypeError):
        return []


__all__ = ["SyllableMapSource"]
