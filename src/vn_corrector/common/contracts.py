"""Cross-stage pipeline DTOs — the M4 → M5 → M6 contract.

These types define the data that flows between Stage-4 (candidates),
Stage-5 (scorer), and Stage-6 (decision).  They are **not** persisted
or exposed externally — they exist only to formalise the hand-off
between pipeline stages.

Data flow::

    Stage 4                     Stage 5                     Stage 6
    ────────                    ────────                    ────────
    CandidateWindow       →     CandidateWindow       →     (unchanged)
    CandidateSequence     →     CandidateSequence     →     (unchanged)
                                ScoreBreakdown         →     ScoredSequence
                                ScoredWindow           →     ScoredWindow
                                TokenCorrectionExplanation

Consumed by
-----------
+---------------------------+------------------------------------------------+
| Type                      | Producers and consumers                        |
+---------------------------+------------------------------------------------+
| ``CandidateWindow``       | Stage-4 windowing → Stage-5 window scorer     |
+---------------------------+------------------------------------------------+
| ``CandidateSequence``     | Stage-4 combinator → Stage-5 ranker           |
+---------------------------+------------------------------------------------+
| ``CorrectionEvidence``    | Stage-5 explainer → embedded in               |
|                           | ``ScoredSequence.explanations``               |
+---------------------------+------------------------------------------------+
| ``TokenCorrectionExpl.``  | Stage-5 explainer → Stage-6 diagnostics       |
+---------------------------+------------------------------------------------+
| ``ScoredSequence``        | Stage-5 ranker → Stage-6 decision engine      |
+---------------------------+------------------------------------------------+
| ``ScoredWindow``          | Stage-5 ranker → Stage-6 decision engine      |
+---------------------------+------------------------------------------------+
| ``MetadataValue``         | Type alias used inside ``CorrectionEvidence`` |
+---------------------------+------------------------------------------------+

Related modules
---------------
* :mod:`vn_corrector.common.scoring` — ``ScoreBreakdown`` (nested in ``ScoredSequence``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vn_corrector.common.scoring import ScoreBreakdown

MetadataValue = str | int | float | bool | None


@dataclass(frozen=True)
class CandidateWindow:
    """A bounded window of tokens around an ambiguous position.

    Stage-4 windower splits the token stream into non-overlapping windows,
    each containing one ambiguous token plus its left/right context.
    Stage-5 uses this to generate combinatorial sequences.

    Parameters
    ----------
    start : int
        Index of the first token in the window.
    end : int
        Index one past the last token (Python slice convention).
    token_candidates : list[Any]
        Per-position candidate lists.  Each element is a list of candidate
        strings for that position.  Positions with only one candidate
        (identity) contain a single-element list.
    """

    start: int
    end: int
    token_candidates: list[Any]


@dataclass(frozen=True)
class CandidateSequence:
    """A concrete candidate path through a :class:`CandidateWindow`.

    Stage-4 combinator generates every combination of per-position
    candidates and records which positions were changed from the original.

    Parameters
    ----------
    tokens : tuple[str, ...]
        The candidate strings for each position in the window.
    original_tokens : tuple[str, ...]
        The original token strings (for diffing).
    changed_positions : tuple[int, ...]
        Indices (into ``tokens``) where ``tokens[i] != original_tokens[i]``.
    """

    tokens: tuple[str, ...]
    original_tokens: tuple[str, ...]
    changed_positions: tuple[int, ...]


@dataclass(frozen=True)
class CorrectionEvidence:
    """A single piece of evidence justifying a token-level correction.

    Produced by Stage-5 scorer explainers.  Each evidence item describes
    one signal that contributed to or detracted from the final score.

    Parameters
    ----------
    kind : str
        Signal name — e.g. ``"word_validity"``, ``"phrase_ngram"``.
    message : str
        Human-readable explanation of this signal's effect.
    score_delta : float
        How much this signal added or subtracted from the total.
    metadata : dict[str, MetadataValue]
        Optional structured data (e.g., matched phrase, ngram score).
    """

    kind: str
    message: str
    score_delta: float = 0.0
    metadata: dict[str, MetadataValue] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenCorrectionExplanation:
    """Explain why a single token was changed.

    Aggregates all :class:`CorrectionEvidence` for one token position.

    Parameters
    ----------
    index : int
        Position in the original token sequence.
    original : str
        The original (uncorrected) token text.
    corrected : str
        The selected (corrected) token text.
    evidence : list[CorrectionEvidence]
        All signals that influenced this correction.
    """

    index: int
    original: str
    corrected: str
    evidence: list[CorrectionEvidence]


@dataclass(frozen=True)
class ScoredSequence:
    r"""A scored candidate sequence with full breakdown and explanations.

    This is the primary output of Stage-5 per-window ranking.  Each window
    produces zero or more ``ScoredSequence``\s ordered by ``score``.

    Parameters
    ----------
    sequence : CandidateSequence
        The candidate path that was scored.
    breakdown : ScoreBreakdown
        The 8-component score that produced ``confidence``.
    confidence : float
        Final confidence (0-1) for this sequence.
    explanations : list[TokenCorrectionExplanation]
        Per-token evidence for explainability / diagnostics.

    See also
    --------
    :class:`ScoreBreakdown` — the additive + penalty decomposition.
    """

    sequence: CandidateSequence
    breakdown: ScoreBreakdown
    confidence: float
    explanations: list[TokenCorrectionExplanation] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.breakdown.total


@dataclass(frozen=True)
class ScoredWindow:
    """Ranking result for a single :class:`CandidateWindow`.

    Produced by Stage-5 per-window ranking and consumed by Stage-6
    decision engine.

    Parameters
    ----------
    window : CandidateWindow
        The original window definition (unchanged from Stage 4).
    ranked_sequences : list[ScoredSequence]
        All scored sequences, sorted descending by ``score``.

    See also
    --------
    :attr:`best` — shorthand for ``ranked_sequences[0]`` if non-empty.
    """

    window: CandidateWindow
    ranked_sequences: list[ScoredSequence]

    @property
    def best(self) -> ScoredSequence | None:
        return self.ranked_sequences[0] if self.ranked_sequences else None
