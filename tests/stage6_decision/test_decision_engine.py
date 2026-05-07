"""Tests for the M6 DecisionEngine — deterministic policy layer."""

from dataclasses import dataclass, field
from typing import cast

from pytest import approx

from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
)
from vn_corrector.stage6_decision.decision import DecisionEngine
from vn_corrector.stage6_decision.types import (
    DecisionReason,
    DecisionType,
)

# ---------------------------------------------------------------------------
# Test 1 — accepts safe correction
# ---------------------------------------------------------------------------


class TestAcceptSafeCorrection:
    def test_accepts_high_confidence(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="ban",
            best="bán",
            best_score=0.92,
            second_best="bàn",
            second_score=0.60,
        )
        assert decision.decision == DecisionType.ACCEPT
        assert decision.reason == DecisionReason.ACCEPTED
        assert decision.margin == approx(0.32)

    def test_accepts_at_threshold(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="ban",
            best="bán",
            best_score=0.85,
            second_best="bàn",
            second_score=0.65,
            protected=False,
        )
        assert decision.decision == DecisionType.ACCEPT
        assert decision.reason == DecisionReason.ACCEPTED
        assert decision.margin == approx(0.20)


# ---------------------------------------------------------------------------
# Test 2 — rejects protected token
# ---------------------------------------------------------------------------


class TestRejectProtected:
    def test_rejects_protected(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="0987654321",
            best="098765432I",
            best_score=0.95,
            second_best="0987654321",
            second_score=0.30,
            protected=True,
        )
        assert decision.decision == DecisionType.REJECT
        assert decision.best == "0987654321"  # falls back to original
        assert decision.reason == DecisionReason.PROTECTED

    def test_protected_identity(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="DHA",
            best="DHA",
            best_score=0.95,
            protected=True,
        )
        assert decision.decision == DecisionType.REJECT
        assert decision.reason == DecisionReason.PROTECTED


# ---------------------------------------------------------------------------
# Test 3 — rejects identity (no change)
# ---------------------------------------------------------------------------


class TestRejectIdentity:
    def test_rejects_unchanged(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="nhà",
            best="nhà",
            best_score=0.90,
            second_best="nha",
            second_score=0.40,
        )
        assert decision.decision == DecisionType.REJECT
        assert decision.reason == DecisionReason.IDENTITY

    def test_rejects_identity_with_no_second(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="nhà",
            best="nhà",
            best_score=0.90,
        )
        assert decision.decision == DecisionType.REJECT
        assert decision.reason == DecisionReason.IDENTITY


# ---------------------------------------------------------------------------
# Test 4 — flags low confidence
# ---------------------------------------------------------------------------


class TestFlagLowConfidence:
    def test_flags_below_threshold(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="ban",
            best="bán",
            best_score=0.70,
            second_best="bàn",
            second_score=0.20,
        )
        assert decision.decision == DecisionType.FLAG
        assert decision.reason == DecisionReason.LOW_CONFIDENCE

    def test_flags_well_below_threshold(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="xyz",
            best="xyz123",
            best_score=0.30,
            second_best=None,
            second_score=0.0,
        )
        assert decision.decision == DecisionType.FLAG
        assert decision.reason == DecisionReason.LOW_CONFIDENCE


# ---------------------------------------------------------------------------
# Test 5 — flags ambiguous candidate
# ---------------------------------------------------------------------------


class TestFlagAmbiguous:
    def test_flags_tight_margin(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="ban",
            best="bán",
            best_score=0.90,
            second_best="bàn",
            second_score=0.84,
        )
        assert decision.decision == DecisionType.FLAG
        assert decision.reason == DecisionReason.AMBIGUOUS
        assert decision.margin == approx(0.06)

    def test_flags_at_ambiguous_boundary(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="dan",
            best="dẫn",
            best_score=0.87,
            second_best="dần",
            second_score=0.78,
        )
        margin = 0.09
        assert margin < 0.10
        decision = engine.decide_token(
            original="dan",
            best="dẫn",
            best_score=0.87,
            second_best="dần",
            second_score=0.78,
        )
        assert decision.decision == DecisionType.FLAG
        assert decision.reason == DecisionReason.AMBIGUOUS


# ---------------------------------------------------------------------------
# Test 6 — needs context (medium margin)
# ---------------------------------------------------------------------------


class TestNeedContext:
    def test_need_context_medium_margin(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="ban",
            best="bán",
            best_score=0.90,
            second_best="bàn",
            second_score=0.75,
        )
        assert decision.decision == DecisionType.NEED_CONTEXT
        assert decision.reason == DecisionReason.NEEDS_CONTEXT
        assert decision.margin == approx(0.15)

    def test_need_context_low_end(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="dan",
            best="dẫn",
            best_score=0.86,
            second_best="dần",
            second_score=0.67,
        )
        assert decision.decision == DecisionType.NEED_CONTEXT
        assert decision.margin == approx(0.19)

    def test_need_context_high_end(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="dan",
            best="dẫn",
            best_score=0.85,
            second_best="dần",
            second_score=0.66,
        )
        assert decision.decision == DecisionType.NEED_CONTEXT
        assert decision.margin == approx(0.19)


# ---------------------------------------------------------------------------
# Test 7 — empty ranked sequence
# ---------------------------------------------------------------------------


class TestEmptyRankedSequence:
    def test_no_ranked_sequences(self):
        engine = DecisionEngine()
        scored_window = ScoredWindow(
            window=CandidateWindow(
                start=0,
                end=12,
                token_candidates=cast(
                    "list[TokenCandidates]",
                    [
                        _make_tc("ban", 0),
                        _make_tc("nha", 1),
                    ],
                ),
            ),
            ranked_sequences=[],
        )
        decisions = engine.decide_window(scored_window)
        assert len(decisions) == 2
        for d in decisions:
            assert d.decision == DecisionType.REJECT
            assert d.reason == DecisionReason.NO_RANKED_SEQUENCE
            assert d.best is None

    def test_no_candidate(self):
        engine = DecisionEngine()
        decision = engine.decide_token(
            original="xyz",
            best=None,
            best_score=0.0,
        )
        assert decision.decision == DecisionType.REJECT
        assert decision.reason == DecisionReason.NO_CANDIDATE
        assert decision.best is None


# ---------------------------------------------------------------------------
# Test 8 — proper token-level second-best
# ---------------------------------------------------------------------------


class TestTokenLevelSecondBest:
    def test_skips_same_token_in_second_best(self):
        """Second-best must differ from best token at that position."""
        seq1 = _make_seq(("tôi", "bán", "nhà"), ("tôi", "ban", "nhà"), 0.93)
        seq2 = _make_seq(("tôi", "bán", "nha"), ("tôi", "ban", "nhà"), 0.89)
        seq3 = _make_seq(("tôi", "bàn", "nhà"), ("tôi", "ban", "nhà"), 0.70)

        window = CandidateWindow(
            start=0,
            end=14,
            token_candidates=cast(
                "list[TokenCandidates]",
                [
                    _make_tc("tôi", 0),
                    _make_tc("ban", 1),
                    _make_tc("nhà", 2),
                ],
            ),
        )
        scored = ScoredWindow(
            window=window,
            ranked_sequences=[seq1, seq2, seq3],
        )
        engine = DecisionEngine()
        decisions = engine.decide_window(scored)

        # Position 1 (index 1): "bán" is best, second-best should be "bàn" (0.70), not "bán" (0.89)
        d = decisions[1]
        assert d.original == "ban"
        assert d.best == "bán"
        assert d.second_best == "bàn"
        assert d.second_score == approx(0.70)
        assert d.decision == DecisionType.ACCEPT
        assert d.margin == approx(0.23)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeTokenCandidates:
    """Minimal token candidates stub for testing."""

    token_text: str
    token_index: int
    protected: bool
    candidates: list[object] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)


def _make_tc(text: str, index: int, protected: bool = False) -> FakeTokenCandidates:
    return FakeTokenCandidates(
        token_text=text,
        token_index=index,
        protected=protected,
        candidates=[],
    )


def _make_seq(
    tokens: tuple[str, ...],
    originals: tuple[str, ...],
    confidence: float,
) -> ScoredSequence:
    changed = tuple(i for i, (t, o) in enumerate(zip(tokens, originals, strict=False)) if t != o)
    return ScoredSequence(
        sequence=CandidateSequence(
            tokens=tokens,
            original_tokens=originals,
            changed_positions=changed,
        ),
        breakdown=ScoreBreakdown(),
        confidence=confidence,
        explanations=[],
    )
