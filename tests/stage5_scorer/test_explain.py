"""Tests for explanation formatting."""

from __future__ import annotations

from vn_corrector.stage5_scorer.explain import format_explanation
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CorrectionEvidence,
    ScoreBreakdown,
    ScoredSequence,
    TokenCorrectionExplanation,
)


class TestFormatExplanation:
    def test_format_basic(self) -> None:
        seq = CandidateSequence(
            tokens=("số", "muỗng", "gạt", "ngang"),
            original_tokens=("số", "mùông", "gạt", "ngang"),
            changed_positions=(1,),
        )
        breakdown = ScoreBreakdown(
            word_validity=4.0,
            phrase_ngram=2.5,
            ocr_confusion=1.0,
            edit_distance=0.5,
            overcorrection_penalty=0.0,
            negative_phrase_penalty=0.0,
        )
        explanations = [
            TokenCorrectionExplanation(
                index=1,
                original="mùông",
                corrected="muỗng",
                evidence=[
                    CorrectionEvidence(
                        kind="ocr_confusion",
                        message="OCR support",
                        score_delta=1.0,
                    ),
                    CorrectionEvidence(
                        kind="edit_distance",
                        message="Distance 1",
                        score_delta=0.5,
                    ),
                ],
            ),
        ]
        scored = ScoredSequence(
            sequence=seq,
            breakdown=breakdown,
            confidence=0.85,
            explanations=explanations,
        )
        result = format_explanation(scored)
        assert "mùông" in result
        assert "muỗng" in result
        assert "ocr_confusion" in result
        assert "word_validity" in result

    def test_format_no_changes(self) -> None:
        seq = CandidateSequence(
            tokens=("a", "b"),
            original_tokens=("a", "b"),
            changed_positions=(),
        )
        scored = ScoredSequence(
            sequence=seq,
            breakdown=ScoreBreakdown(),
            confidence=1.0,
            explanations=[],
        )
        result = format_explanation(scored)
        assert "No changes" in result or "no changes" in result
