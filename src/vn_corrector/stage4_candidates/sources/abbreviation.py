"""Abbreviation source — expands known abbreviations to their full forms."""

from __future__ import annotations

from collections.abc import Iterable

from vn_corrector.stage4_candidates.sources.base import CandidateSourceGenerator
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)


class AbbreviationSource(CandidateSourceGenerator):
    """Generate candidates by expanding known abbreviations.

    Uses the lexicon's abbreviation entries. Multi-token expansions
    record ``replacement_token_count > 1`` in the proposal metadata
    so the downstream generator can set ``replacement_token_count``.
    """

    source = CandidateSource.ABBREVIATION

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        lexicon = context.lexicon
        prior_weight = context.config.source_prior_weights.get(CandidateSource.ABBREVIATION, 0.15)

        try:
            result = lexicon.lookup_abbreviation(request.token_text)
            if not result or not result.entries:
                return
        except (AttributeError, TypeError):
            return

        for entry in result.entries:
            expansions = getattr(entry, "expansions", ())
            domain = getattr(entry, "domain", None)
            for expansion in expansions:
                if expansion == request.token_text:
                    continue
                token_count = len(expansion.split())
                yield CandidateProposal(
                    text=expansion,
                    source=CandidateSource.ABBREVIATION,
                    evidence=CandidateEvidence(
                        source=CandidateSource.ABBREVIATION,
                        detail=f"abbreviation: {request.token_text} -> {expansion}",
                        matched_text=expansion,
                        metadata={
                            "expansion": expansion,
                            "domain": domain,
                            "replacement_token_count": token_count,
                        },
                    ),
                    prior_score=prior_weight,
                )


__all__ = ["AbbreviationSource"]
