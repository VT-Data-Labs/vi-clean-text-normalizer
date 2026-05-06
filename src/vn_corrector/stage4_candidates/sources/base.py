"""Abstract protocol for source-level candidate generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING

from vn_corrector.stage4_candidates.types import (
    CandidateEvidence,
    CandidateProposal,
    CandidateRequest,
    CandidateSource,
)

if TYPE_CHECKING:
    from vn_corrector.stage4_candidates.types import CandidateContext


class CandidateSourceGenerator(ABC):
    """Abstract base for a single candidate source.

    Each subclass implements :meth:`generate` for one source type
    (e.g. OCR confusion, syllable map, abbreviation expansion).
    """

    source: CandidateSource

    @abstractmethod
    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        """Yield candidate proposals for *request* given *context*.

        Args:
            request: The token being processed.
            context: Global context including lexicon, config, and sibling tokens.

        Yields:
            CandidateProposal for each valid variant found.
        """


class IdentitySource(CandidateSourceGenerator):
    """Always yields the original token as a candidate.

    This is the simplest source and serves as the identity fallback.
    """

    source = CandidateSource.ORIGINAL

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        yield CandidateProposal(
            text=request.token_text,
            source=CandidateSource.ORIGINAL,
            evidence=CandidateEvidence(
                source=CandidateSource.ORIGINAL,
                detail="identity_candidate",
            ),
            prior_score=getattr(context.config, "source_prior_weights", {}).get(
                CandidateSource.ORIGINAL, 0.10
            ),
        )


__all__ = [
    "CandidateSourceGenerator",
    "IdentitySource",
]
