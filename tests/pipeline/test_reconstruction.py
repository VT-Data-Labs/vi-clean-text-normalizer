"""Tests for offset-based text reconstruction."""

from __future__ import annotations

from vn_corrector.common.correction import CorrectionChange
from vn_corrector.common.enums import CandidateIndexSource, ChangeReason
from vn_corrector.common.spans import TextSpan
from vn_corrector.pipeline.reconstruction import apply_changes, resolve_overlapping_changes


def _make_change(
    original: str,
    replacement: str,
    start: int,
    end: int,
    confidence: float = 0.9,
) -> CorrectionChange:
    return CorrectionChange(
        original=original,
        replacement=replacement,
        span=TextSpan(start=start, end=end),
        confidence=confidence,
        reason=ChangeReason.DIACRITIC_RESTORED,
        candidate_sources=(CandidateIndexSource.NO_TONE_INDEX,),
    )


class TestApplyChanges:
    def test_no_changes(self) -> None:
        assert apply_changes("hello world", []) == "hello world"

    def test_single_change(self) -> None:
        changes = [_make_change("world", "there", start=6, end=11)]
        assert apply_changes("hello world", changes) == "hello there"

    def test_multiple_non_overlapping(self) -> None:
        changes = [
            _make_change("hello", "hi", start=0, end=5),
            _make_change("world", "there", start=6, end=11),
        ]
        assert apply_changes("hello world", changes) == "hi there"

    def test_punctuation_preserved(self) -> None:
        changes = [_make_change("world", "there", start=6, end=11)]
        assert apply_changes("hello world!", changes) == "hello there!"

    def test_whitespace_preserved(self) -> None:
        changes = [_make_change("hello", "hi", start=0, end=5)]
        assert apply_changes("hello   world", changes) == "hi   world"

    def test_empty_text(self) -> None:
        assert apply_changes("", []) == ""

    def test_replacement_spans_different_lengths(self) -> None:
        changes = [_make_change("abc", "longer", start=0, end=3)]
        assert apply_changes("abc def", changes) == "longer def"

    def test_first_token_only(self) -> None:
        changes = [_make_change("neu", "nếu", start=0, end=3)]
        result = apply_changes("neu do am", changes)
        assert result == "nếu do am"


class TestResolveOverlapping:
    def test_empty_input(self) -> None:
        assert resolve_overlapping_changes([]) == []

    def test_no_overlap(self) -> None:
        changes = [
            _make_change("a", "x", start=0, end=1),
            _make_change("b", "y", start=2, end=3),
        ]
        assert len(resolve_overlapping_changes(changes)) == 2

    def test_overlapping_keeps_higher_confidence(self) -> None:
        changes = [
            _make_change("b", "y", start=1, end=2, confidence=0.5),
            _make_change("ab", "xy", start=0, end=2, confidence=0.9),
        ]
        resolved = resolve_overlapping_changes(changes)
        assert len(resolved) == 1
        assert resolved[0].replacement == "xy"

    def test_adjacent_spans_not_overlapping(self) -> None:
        changes = [
            _make_change("a", "x", start=0, end=1),
            _make_change("b", "y", start=1, end=2),
        ]
        assert len(resolve_overlapping_changes(changes)) == 2

    def test_ordered_by_start(self) -> None:
        changes = [
            _make_change("b", "y", start=2, end=3),
            _make_change("a", "x", start=0, end=1),
        ]
        resolved = resolve_overlapping_changes(changes)
        assert resolved[0].span.start < resolved[1].span.start
