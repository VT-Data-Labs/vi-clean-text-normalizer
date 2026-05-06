"""OCR confusion source — applies known confusion maps to generate variants."""

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


class OcrConfusionSource(CandidateSourceGenerator):
    """Generate candidates by applying OCR confusion replacements.

    Uses the lexicon's OCR confusion map (noisy -> corrections).
    Limits replacement depth to ``max_ocr_replacements_per_token``.
    """

    source = CandidateSource.OCR_CONFUSION

    def generate(
        self,
        request: CandidateRequest,
        context: CandidateContext,
    ) -> Iterable[CandidateProposal]:
        if request.protected:
            return

        config = context.config
        max_repl = config.max_ocr_replacements_per_token
        lexicon = context.lexicon

        # Try lexicon OCR lookup
        try:
            corrections = lexicon.get_ocr_corrections(request.token_text)
            candidate_texts: list[str] = list(corrections.corrections)
        except (AttributeError, TypeError):
            # Fallback to lookup_ocr
            try:
                raw = lexicon.lookup_ocr(request.token_text)
                candidate_texts = list(raw) if raw else []
            except (AttributeError, TypeError):
                return

        if not candidate_texts:
            return

        prior_weight = config.source_prior_weights.get(CandidateSource.OCR_CONFUSION, 0.30)

        for text in candidate_texts[:max_repl]:
            if text == request.token_text:
                continue
            yield CandidateProposal(
                text=text,
                source=CandidateSource.OCR_CONFUSION,
                evidence=CandidateEvidence(
                    source=CandidateSource.OCR_CONFUSION,
                    detail=f"ocr_confusion: {request.token_text} -> {text}",
                    confidence_hint=0.7,
                    metadata={
                        "original": request.token_text,
                        "replacement": text,
                    },
                ),
                prior_score=prior_weight,
            )


__all__ = ["OcrConfusionSource"]
