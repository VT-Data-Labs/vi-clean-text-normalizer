"""M5 — N-Gram Phrase Scorer.

This package provides the first context-aware ranking layer for the
Vietnamese correction pipeline.  It consumes M4 ``TokenCandidates``,
builds bounded windows around ambiguous tokens, generates candidate
sequences, and scores them using phrase n-gram evidence, domain context,
OCR confusion support, and overcorrection prevention.
"""

from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.diagnostics import format_scored_window
from vn_corrector.stage5_scorer.explain import format_explanation
from vn_corrector.stage5_scorer.scorer import PhraseScorer
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    MetadataValue,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
    TokenCorrectionExplanation,
)
from vn_corrector.stage5_scorer.weights import ScoringWeights

__all__ = [
    "CandidateSequence",
    "CandidateWindow",
    "CorrectionEvidence",
    "MetadataValue",
    "PhraseScorer",
    "PhraseScorerConfig",
    "ScoreBreakdown",
    "ScoredSequence",
    "ScoredWindow",
    "ScoringWeights",
    "TokenCorrectionExplanation",
    "format_explanation",
    "format_scored_window",
]
