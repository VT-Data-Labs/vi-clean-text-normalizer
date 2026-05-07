r"""Pipeline output types — decisions, changes, flags, and final results.

These are the public-facing types that Stage-6 produces.  Every correction
run ultimately produces a :class:`CorrectionResult` containing a list of
applied :class:`CorrectionChange`\s and any :class:`CorrectionFlag`\s.

Consumed by
-----------
+----------------------+----------------------------------------------------+
| Type                 | Produced by / consumed by                           |
+----------------------+----------------------------------------------------+
| ``CorrectionDecision``| Stage-6 ``DecisionEngine.decide_token()`` — one   |
|                      | per ambiguous position.  Embeds the winner, margin,|
|                      | and reason code.                                   |
+----------------------+----------------------------------------------------+
| ``CorrectionChange`` | Stage-6 change builder — a concrete ``replace this |
|                      | span with this text`` instruction.                 |
+----------------------+----------------------------------------------------+
| ``CorrectionFlag``   | Stage-6 flag builder — raised when the engine      |
|                      | wants to warn about low-confidence or ambiguous    |
|                      | corrections.                                       |
+----------------------+----------------------------------------------------+
| ``CorrectionResult`` | Top-level return value of the full pipeline.       |
|                      | Contains the corrected text, all changes, flags,   |
|                      | and overall confidence.                            |
+----------------------+----------------------------------------------------+

Related modules
---------------
* :mod:`vn_corrector.common.enums` — ``DecisionType``, ``FlagType``,
  ``ChangeReason``, ``CandidateIndexSource``
* :mod:`vn_corrector.common.spans` — ``TextSpan`` (change/flag positions)
* ``lexicon/types.py`` — ``LexiconCandidate`` (flag attachments)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from vn_corrector.common.enums import (
    CandidateIndexSource,
    ChangeReason,
    DecisionType,
    FlagType,
)
from vn_corrector.common.lexicon import LexiconCandidate
from vn_corrector.common.spans import TextSpan


@dataclass(frozen=True, slots=True)
class CorrectionDecision:
    """Decision metadata for a single token position.

    Records which candidate won, the margin over the runner-up, and
    the policy reason (accept / reject / flag).

    See also
    --------
    :class:`DecisionType` — accept / reject / flag / need_context.
    :class:`DecisionReason` — stable reason codes.
    """

    original: str
    best: str | None
    best_score: float
    second_best: str | None = None
    second_score: float = 0.0
    margin: float = 0.0
    decision: DecisionType = DecisionType.FLAG
    reason: str = ""
    candidate_sources: tuple[CandidateIndexSource, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not 0.0 <= self.best_score <= 1.0:
            raise ValueError("best_score must be between 0 and 1")
        if not 0.0 <= self.second_score <= 1.0:
            raise ValueError("second_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class CorrectionChange:
    """A single applied correction — ``original`` → ``replacement`` at a ``TextSpan``.

    Produced by the Stage-6 change builder whenever the pipeline decides
    to alter the text.  The ``reason`` field (a :class:`ChangeReason`) explains
    the kind of fix (diacritic restoration, OCR fix, expansion, etc.).

    See also
    --------
    :class:`ChangeReason` — tags describing what kind of change.
    :class:`CorrectionDecision` — the policy decision that justified this change.
    """

    original: str
    replacement: str
    span: TextSpan
    confidence: float
    reason: ChangeReason
    decision: CorrectionDecision | None = None
    candidate_sources: tuple[CandidateIndexSource, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.original == "":
            raise ValueError("original must not be empty")
        if self.replacement == "":
            raise ValueError("replacement must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        self.span.validate()


@dataclass(frozen=True, slots=True)
class CorrectionFlag:
    """A warning raised during correction for human review.

    Unlike :class:`CorrectionChange`, a flag does **not** alter the text.
    It records a potential issue (unknown token, ambiguous candidates,
    low confidence, OCR suspect, etc.) so that callers can surface it.

    See also
    --------
    :class:`FlagType` — categories: unknown_token, ambiguous_candidates, etc.
    """

    span_text: str
    span: TextSpan
    flag_type: FlagType
    candidates: tuple[LexiconCandidate, ...] = field(default_factory=tuple)
    reason: str = ""
    severity: Literal["info", "warning", "error"] = "warning"

    def validate(self) -> None:
        if self.span_text == "":
            raise ValueError("span_text must not be empty")
        self.span.validate()


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    r"""Top-level output of a full correction pass.

    Contains the corrected text, overall confidence score, a list of
    every applied :class:`CorrectionChange`, and any :class:`CorrectionFlag`\s
    that were raised.

    This is the primary return type of the public correction API.
    """

    original_text: str
    corrected_text: str
    confidence: float
    changes: tuple[CorrectionChange, ...] = field(default_factory=tuple)
    flags: tuple[CorrectionFlag, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
