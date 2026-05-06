"""Tests for the M5 phrase scorer core types."""

from __future__ import annotations

import pytest

from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
)


class TestScoreBreakdown:
    def test_total_no_penalties(self) -> None:
        b = ScoreBreakdown(word_validity=1.0, syllable_freq=0.5, phrase_ngram=1.0)
        assert b.total == pytest.approx(2.5)

    def test_total_with_penalties(self) -> None:
        b = ScoreBreakdown(
            word_validity=1.0,
            phrase_ngram=1.0,
            overcorrection_penalty=0.5,
        )
        assert b.total == pytest.approx(1.5)

    def test_total_empty(self) -> None:
        assert ScoreBreakdown().total == pytest.approx(0.0)

    def test_total_negative(self) -> None:
        b = ScoreBreakdown(overcorrection_penalty=3.0, negative_phrase_penalty=2.0)
        assert b.total == pytest.approx(-5.0)


class TestScoredSequence:
    def test_score_property(self) -> None:
        b = ScoreBreakdown(word_validity=2.0)
        seq = CandidateSequence(tokens=("a",), original_tokens=("a",), changed_positions=())
        s = ScoredSequence(sequence=seq, breakdown=b, confidence=0.8)
        assert s.score == pytest.approx(2.0)


class TestScoredWindow:
    def test_best_with_sequences(self) -> None:
        seq = CandidateSequence(tokens=("a",), original_tokens=("a",), changed_positions=())
        w = ScoredWindow(
            window=CandidateWindow(start=0, end=1, token_candidates=[]),
            ranked_sequences=[
                ScoredSequence(
                    sequence=seq,
                    breakdown=ScoreBreakdown(word_validity=2.0),
                    confidence=0.9,
                ),
                ScoredSequence(
                    sequence=seq,
                    breakdown=ScoreBreakdown(word_validity=1.0),
                    confidence=0.5,
                ),
            ],
        )
        assert w.best is not None
        assert w.best.score == pytest.approx(2.0)

    def test_best_empty(self) -> None:
        w = ScoredWindow(
            window=CandidateWindow(start=0, end=1, token_candidates=[]),
            ranked_sequences=[],
        )
        assert w.best is None


class TestCandidateWindow:
    def test_fields(self) -> None:
        w = CandidateWindow(start=0, end=2, token_candidates=[])
        assert w.start == 0
        assert w.end == 2
        assert w.token_candidates == []


class TestCandidateSequence:
    def test_changed_positions(self) -> None:
        s = CandidateSequence(
            tokens=("x", "y"),
            original_tokens=("a", "b"),
            changed_positions=(0, 1),
        )
        assert s.tokens == ("x", "y")
        assert s.changed_positions == (0, 1)

    def test_no_changes(self) -> None:
        s = CandidateSequence(
            tokens=("a", "b"),
            original_tokens=("a", "b"),
            changed_positions=(),
        )
        assert s.changed_positions == ()
        assert s.tokens == s.original_tokens


class TestCorrectionEvidence:
    def test_defaults(self) -> None:
        ev = CorrectionEvidence(kind="test", message="msg")
        assert ev.score_delta == 0.0
        assert ev.metadata == {}
