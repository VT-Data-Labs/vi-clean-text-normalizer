"""Core pipeline — protect, mask, restore, conflict resolution.

The engine operates solely on ``Matcher`` and ``Span`` objects.
It has **no** knowledge of regex, YAML, or lexicon files — those are
handled by ``registry.py`` and the ``matchers/`` subpackage.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from vn_corrector.common.types import ProtectedDocument, Span, SpanType
from vn_corrector.stage3_protect.matchers.base import Matcher

# ---------------------------------------------------------------------------
# Placeholder constants
# ---------------------------------------------------------------------------

PH_LEFT = "⟪"
PH_RIGHT = "⟫"


def make_placeholder(span_type: SpanType, idx: int) -> str:
    """Build a collision-safe placeholder for a span."""
    return f"{PH_LEFT}{span_type.upper()}_{idx}{PH_RIGHT}"


# ---------------------------------------------------------------------------
# Conflict resolution
# ---------------------------------------------------------------------------


def resolve_conflicts(candidates: list[Span], text_length: int) -> list[Span]:
    """Resolve overlapping spans via greedy selection.

    Rules (applied in sort order):
    1. Higher priority wins
    2. Same priority → longer span wins
    3. Still tied → earlier in text wins

    Then a greedy sweep picks non-overlapping spans.
    """
    if not candidates:
        return []

    candidates.sort(key=lambda s: (s.start, -s.priority, -(s.end - s.start)))

    occupied = [False] * text_length
    final: list[Span] = []

    for span in candidates:
        if span.start < 0 or span.end > text_length:
            continue
        if any(occupied[span.start : span.end]):
            continue
        final.append(span)
        for i in range(span.start, span.end):
            occupied[i] = True

    return final


# ---------------------------------------------------------------------------
# Mask / Restore
# ---------------------------------------------------------------------------


def mask(text: str, spans: list[Span]) -> tuple[str, dict[str, str]]:
    """Replace protected spans in *text* with placeholders.

    Returns the masked string and a ``{placeholder: original_value}`` map.
    Spans must already be final (non-overlapping, sorted by start).
    """
    sorted_spans = sorted(spans, key=lambda s: s.start)

    result: list[str] = []
    last = 0
    placeholder_map: dict[str, str] = {}
    counters: dict[str, int] = defaultdict(int)

    for span in sorted_spans:
        result.append(text[last : span.start])
        idx = counters[span.type.value]
        ph = make_placeholder(span.type, idx)
        counters[span.type.value] += 1
        result.append(ph)
        placeholder_map[ph] = span.value
        last = span.end

    result.append(text[last:])
    return "".join(result), placeholder_map


def restore(masked_text: str, placeholder_map: dict[str, str]) -> str:
    """Replace placeholders with their original values.

    Guarantees: ``restore(*mask(text, spans)) == text``.
    """
    result = masked_text
    for placeholder, value in placeholder_map.items():
        result = result.replace(placeholder, value)
    return result


# ---------------------------------------------------------------------------
# Public API — protect
# ---------------------------------------------------------------------------


def protect(text: str, matchers: Sequence[Matcher]) -> ProtectedDocument:
    """Protect detected spans in *text* using the supplied *matchers*.

    Returns a ``ProtectedDocument`` with the masked text, final spans,
    placeholder map, and debug info.

    Invariant: ``restore(doc.masked_text, doc.placeholder_map) == doc.original_text``
    """
    candidates: list[Span] = []
    for matcher in matchers:
        candidates.extend(matcher.find(text))

    final_spans = resolve_conflicts(candidates, len(text))
    masked_text, placeholder_map = mask(text, final_spans)

    return ProtectedDocument(
        original_text=text,
        masked_text=masked_text,
        spans=tuple(final_spans),
        placeholder_map=placeholder_map,
        debug_info={
            "candidate_count": len(candidates),
            "final_span_count": len(final_spans),
        },
    )
