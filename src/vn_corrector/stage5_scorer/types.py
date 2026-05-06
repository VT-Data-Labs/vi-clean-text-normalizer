"""Core types for the M5 phrase scorer.

Every dataclass is frozen for safety and deterministic hashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vn_corrector.stage4_candidates.types import TokenCandidates

MetadataValue = str | int | float | bool | None


# ---------------------------------------------------------------------------
# Score breakdown
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreBreakdown:
    """Decomposed score for a candidate sequence.

    Penalty fields (``overcorrection_penalty``, ``negative_phrase_penalty``)
    are stored as **positive** values and subtracted in ``total``.
    """

    word_validity: float = 0.0
    syllable_freq: float = 0.0
    phrase_ngram: float = 0.0
    domain_context: float = 0.0
    ocr_confusion: float = 0.0
    edit_distance: float = 0.0
    overcorrection_penalty: float = 0.0
    negative_phrase_penalty: float = 0.0

    @property
    def total(self) -> float:
        additions = (
            self.word_validity
            + self.syllable_freq
            + self.phrase_ngram
            + self.domain_context
            + self.ocr_confusion
            + self.edit_distance
        )
        penalties = self.overcorrection_penalty + self.negative_phrase_penalty
        return additions - penalties


# ---------------------------------------------------------------------------
# Window / sequence types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateWindow:
    """A bounded window of tokens around an ambiguous position."""

    start: int
    end: int
    token_candidates: list[TokenCandidates]


@dataclass(frozen=True)
class CandidateSequence:
    """A concrete candidate path through a :class:`CandidateWindow`.

    ``tokens`` holds the chosen text for each position; ``original_tokens``
    is the unchanged text for comparison; ``changed_positions`` lists
    indices where the candidate differs from the original.
    """

    tokens: tuple[str, ...]
    original_tokens: tuple[str, ...]
    changed_positions: tuple[int, ...]


# ---------------------------------------------------------------------------
# Evidence / explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorrectionEvidence:
    """A single piece of evidence justifying a token-level correction."""

    kind: str
    message: str
    score_delta: float = 0.0
    metadata: dict[str, MetadataValue] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenCorrectionExplanation:
    """Explain why a single token was changed."""

    index: int
    original: str
    corrected: str
    evidence: list[CorrectionEvidence]


# ---------------------------------------------------------------------------
# Scored output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoredSequence:
    """A scored candidate sequence with breakdown and explanation."""

    sequence: CandidateSequence
    breakdown: ScoreBreakdown
    confidence: float
    explanations: list[TokenCorrectionExplanation] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.breakdown.total


@dataclass(frozen=True)
class ScoredWindow:
    """Ranking result for a single :class:`CandidateWindow`."""

    window: CandidateWindow
    ranked_sequences: list[ScoredSequence]

    @property
    def best(self) -> ScoredSequence | None:
        return self.ranked_sequences[0] if self.ranked_sequences else None


__all__ = [
    "CandidateSequence",
    "CandidateWindow",
    "CorrectionEvidence",
    "MetadataValue",
    "ScoreBreakdown",
    "ScoredSequence",
    "ScoredWindow",
    "TokenCorrectionExplanation",
]
