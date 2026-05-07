"""Scoring primitives — ``Score`` and ``ScoreBreakdown``.

These are the two numeric foundations of the pipeline:

* :class:`Score` — compact (confidence, frequency, priority) attached to
  every lexicon entry and candidate.  Used for simple ordering.
* :class:`ScoreBreakdown` — eight-component signal used by Stage-5 scorer
  to rank candidate sequences.  The ``total`` property sums additive
  signals and subtracts penalties.

Consumed by
-----------
+-------------------+----------------------------------------------------+
| Type              | Stages using it                                    |
+-------------------+----------------------------------------------------+
| ``Score``         | Stage-2 lexicon entries (``lexicon/types.py``),    |
|                   | Stage-4 candidate generation.                      |
+-------------------+----------------------------------------------------+
| ``ScoreBreakdown``| Stage-5 scorer, Stage-6 decision engine.           |
|                   | Embedded in :class:`~vn_corrector.common.contracts.|
|                   | ScoredSequence`.                                   |
+-------------------+----------------------------------------------------+

Related modules
---------------
* :mod:`vn_corrector.common.contracts` — ``ScoredSequence.breakdown: ScoreBreakdown``
* ``lexicon/types.py`` — ``LexiconEntry.score: Score``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Score:
    """Compact numeric profile for a lexicon entry or candidate.

    Parameters
    ----------
    confidence : float
        How reliable this entry is (0-1).  Built-in data defaults to 1.0;
        OCR-reviewed entries may be lower.
    frequency : float
        Relative frequency in a reference corpus (≥0).  Higher = more common.
    priority : int
        Tie-breaker; higher = preferred when confidence+freq are equal.
    """

    confidence: float = 1.0
    frequency: float = 0.0
    priority: int = 0

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.frequency < 0:
            raise ValueError("frequency must be >= 0")


@dataclass(frozen=True)
class ScoreBreakdown:
    """Eight-component score for a candidate sequence.

    Six additive signals and two penalty fields.  Use the ``total`` property
    to get the combined value (additives - penalties).

    Additive signals
    ----------------
    * ``word_validity`` — all tokens form valid lexicon words
    * ``syllable_freq`` — average syllable frequency in the sequence
    * ``phrase_ngram`` — n-gram fit against the curated phrase store
    * ``domain_context`` — domain-specific phrase boost
    * ``ocr_confusion`` — evidence from the OCR confusion index
    * ``edit_distance`` — closeness to the original (higher = closer)

    Penalties (stored as **positive** values, subtracted in ``total``)
    -------------------------------------------------------------------
    * ``overcorrection_penalty`` — penalises changing too many tokens
    * ``negative_phrase_penalty`` — penalises known-bad phrases

    See also
    --------
    :class:`~vn_corrector.common.contracts.ScoredSequence` — container that
    pairs a ``ScoreBreakdown`` with a ``CandidateSequence``.
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
