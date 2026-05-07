"""Offset-based text reconstruction for the correction pipeline.

Preserves all original whitespace, punctuation, protected spans, and
non-text characters by working with character offsets rather than
token-level reconstruction.
"""

from __future__ import annotations

from vn_corrector.common.correction import CorrectionChange
from vn_corrector.common.spans import TextSpan


def _changes_overlap(a: TextSpan, b: TextSpan) -> bool:
    """Return ``True`` when two spans overlap."""
    return a.start < b.end and b.start < a.end


def resolve_overlapping_changes(
    changes: list[CorrectionChange],
) -> list[CorrectionChange]:
    """Resolve overlapping changes, keeping the highest-confidence ones.

    Rules:
    1. Sort by confidence descending.
    2. Accept a change only if its span does not overlap already-accepted spans.
    3. Return changes sorted by start offset.

    This prevents double-editing the same token region.
    """
    if not changes:
        return []

    sorted_changes = sorted(changes, key=lambda c: c.confidence, reverse=True)
    accepted: list[CorrectionChange] = []
    used_spans: list[TextSpan] = []

    for change in sorted_changes:
        if not any(_changes_overlap(change.span, used) for used in used_spans):
            accepted.append(change)
            used_spans.append(change.span)

    accepted.sort(key=lambda c: (c.span.start, c.span.end))
    return accepted


def apply_changes(text: str, changes: list[CorrectionChange]) -> str:
    """Reconstruct corrected text by applying changes to *text*.

    Uses original character offsets so whitespace, punctuation, and
    protected content are preserved exactly.

    Parameters
    ----------
    text:
        The input text (normalized or original) to apply changes to.
    changes:
        Sorted, non-overlapping changes with correct ``TextSpan``
        character offsets.

    Returns
    -------
    str
        The text with all changes applied.
    """
    if not changes:
        return text

    pending = sorted(changes, key=lambda c: (c.span.start, c.span.end))
    pieces: list[str] = []
    cursor = 0

    for change in pending:
        if change.span.start < cursor:
            continue
        pieces.append(text[cursor : change.span.start])
        pieces.append(change.replacement)
        cursor = change.span.end

    pieces.append(text[cursor:])
    return "".join(pieces)
