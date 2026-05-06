"""Scoring weights for the M5 phrase scorer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringWeights:
    """Weight coefficients for each scoring signal.

    These are multiplied by the raw signal value before summing into
    the total ScoreBreakdown.  ``overcorrection_penalty`` and
    ``negative_phrase_penalty`` are stored as **positive** values and
    subtracted during ``ScoreBreakdown.total``.
    """

    word_validity: float = 1.0
    syllable_freq: float = 0.4
    phrase_ngram: float = 1.4
    domain_context: float = 1.2
    ocr_confusion: float = 1.0
    edit_distance: float = 0.6
    overcorrection_penalty: float = 1.3
    negative_phrase_penalty: float = 1.5
