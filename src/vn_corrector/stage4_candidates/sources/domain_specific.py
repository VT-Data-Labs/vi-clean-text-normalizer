"""Domain-specific source — pluggable hook for domain lexicon candidates.

This source uses ``LexiconEntry.domain`` to find domain-relevant variants.
No hardcoded business logic lives here; all domain rules are in the lexicon.
"""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.common.lexicon import LexiconEntry
from vn_corrector.stage1_normalize import to_no_tone_key
from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator

# TODO: expose a public Vietnamese-aware edit distance utility.
from vn_corrector.stage4_candidates.sources.edit_distance import _levenshtein
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


class DomainSpecificSource(CandidateSourceGenerator):
    """Generate domain-specific candidates from the lexicon."""

    source = CandidateSource.DOMAIN_SPECIFIC

    def __init__(self, domain: str | None = None) -> None:
        self._domain = domain

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        lexicon = context.lexicon
        prior_weight = context.config.source_prior_weights.get(
            CandidateSource.DOMAIN_SPECIFIC, 0.20
        )

        no_tone = to_no_tone_key(request.token_text)

        try:
            result = lexicon.lookup_accentless(no_tone)
            entries = list(result.entries) if result is not None else []
        except (AttributeError, TypeError):
            return

        surface_entries = [e for e in entries if isinstance(e, (LexiconEntry,))]
        for entry in surface_entries:
            domain = getattr(entry, "domain", None) or getattr(entry, "tags", ())
            if not domain:
                continue
            # Check domain match (if we have a specific domain)
            if self._domain is not None:
                entry_domain = domain if isinstance(domain, str) else ""
                if entry_domain != self._domain and self._domain not in (
                    entry_domain if isinstance(entry_domain, str) else ""
                ):
                    continue

            if entry.surface == request.token_text:
                continue

            freq = getattr(entry, "score", None)
            freq_val = freq.frequency if freq is not None else 0.0
            yield CandidateProposal(
                text=entry.surface,
                source=CandidateSource.DOMAIN_SPECIFIC,
                evidence=CandidateEvidence(
                    source=CandidateSource.DOMAIN_SPECIFIC,
                    detail=f"domain_term: {entry.surface} (domain={domain})",
                    matched_key=no_tone,
                    metadata={
                        "surface": entry.surface,
                        "domain": domain,
                    },
                ),
                prior_score=prior_weight + freq_val * 0.2,
                edit_distance=_levenshtein(request.token_text, entry.surface),
                word_freq=freq_val,
            )


__all__ = ["DomainSpecificSource"]
