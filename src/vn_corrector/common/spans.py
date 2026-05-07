"""Positional spans, tokens, case masks, and protected-document types.

These are the spatial primitives of the pipeline — every correction
decision is anchored to a ``TextSpan`` or ``ProtectedSpan``, and
every tokenised input is a sequence of ``Token`` objects.

Consumed by
-----------
+-------------------+----------------------------------------------------+
| Type              | Stages using it                                    |
+-------------------+----------------------------------------------------+
| ``TextSpan``      | Tokenizer (S0), Stage-4 sources, Stage-6 changes/  |
|                   | flags — any type that needs to point at a region   |
|                   | of the original text.                              |
+-------------------+----------------------------------------------------+
| ``ProtectedSpan`` | Stage-3 matchers (regex, lexicon) and engine —     |
|                   | marks content to be masked before correction.      |
+-------------------+----------------------------------------------------+
| ``ProtectedDocument``  | Stage-3 ``protect()`` return value.  Carries the |
|                   | masked text, placeholder map, and all final spans. |
+-------------------+----------------------------------------------------+
| ``Token``         | Tokenizer (S0) → Stage-4 generator.  Each token    |
|                   | carries its span, type, and normalised forms.      |
+-------------------+----------------------------------------------------+
| ``CaseMask``      | :mod:`vn_corrector.case_mask` — records original   |
|                   | casing so it can be restored after correction.     |
+-------------------+----------------------------------------------------+

Related modules
---------------
* :mod:`vn_corrector.common.enums` — ``TokenType``, ``SpanType``, ``CasePattern``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vn_corrector.common.enums import CasePattern, SpanType, TokenType


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Half-open character interval ``[start, end)`` in the original text.

    Used as the universal coordinate system — every ``Token``,
    ``CorrectionChange``, and ``CorrectionFlag`` carries one.
    """

    start: int
    end: int

    def validate(self) -> None:
        if self.start < 0:
            raise ValueError("span.start must be >= 0")
        if self.end < self.start:
            raise ValueError("span.end must be >= span.start")


@dataclass(frozen=True, slots=True)
class ProtectedSpan:
    """A detected protected region in the original text.

    Produced by Stage-3 matchers (regex, lexicon) and resolved by the
    conflict-resolution engine before masking.

    See also
    --------
    :class:`TextSpan` — simpler start/end pair without type metadata.
    :class:`SpanType` — the kind of content this span represents.
    """

    type: SpanType
    start: int
    end: int
    value: str
    priority: int
    source: str

    def validate(self) -> None:
        if self.start < 0:
            raise ValueError("span.start must be >= 0")
        if self.end <= self.start:
            raise ValueError("span.end must be > span.start")


@dataclass(frozen=True, slots=True)
class ProtectedDocument:
    """Result of a Stage-3 ``protect()`` pass.

    Carries the masked text (with placeholders), the full span list,
    the placeholder→original map, and optional debug info.

    Invariant: ``restore(doc.masked_text, doc.placeholder_map) == doc.original_text``
    """

    original_text: str
    masked_text: str
    spans: tuple[ProtectedSpan, ...]
    placeholder_map: dict[str, str]
    debug_info: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Token:
    """A single token produced by the tokenizer (:mod:`vn_corrector.tokenizer`).

    Carries the original text, its type classification, its position
    (``TextSpan``), and normalised forms used for downstream matching.
    The ``protected`` flag is set when the token overlaps a Stage-3 span.

    See also
    --------
    :class:`TokenType` — classifications: VI_WORD, NUMBER, PUNCT, etc.
    :class:`TextSpan` — the character span this token occupies.
    """

    text: str
    token_type: TokenType
    span: TextSpan
    normalized: str | None = None
    no_tone: str | None = None
    protected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.text == "":
            raise ValueError("token.text must not be empty")
        self.span.validate()


@dataclass(frozen=True, slots=True)
class CaseMask:
    """Original → working case mapping for a single token.

    Produced by :mod:`vn_corrector.case_mask` to record the original
    casing pattern so it can be restored after the correction pass.

    See also
    --------
    :class:`CasePattern` — one of LOWER / UPPER / TITLE / MIXED / UNKNOWN.
    """

    original: str
    working: str
    case_pattern: CasePattern
    uppercase_positions: tuple[int, ...] = field(default_factory=tuple)
