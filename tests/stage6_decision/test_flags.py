"""Tests for M6 flag builder — decision_to_flag."""

from vn_corrector.common.types import (
    CorrectionDecision,
    DecisionType,
    FlagType,
)
from vn_corrector.stage6_decision.flags import decision_to_flag


class TestDecisionToFlag:
    def test_low_confidence_creates_flag(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.70,
            second_best="bàn",
            second_score=0.20,
            margin=0.50,
            decision=DecisionType.FLAG,
            reason="low_confidence",
        )
        flag = decision_to_flag(decision, token_index=0)
        assert flag is not None
        assert flag.span_text == "ban"
        assert flag.flag_type == FlagType.LOW_CONFIDENCE
        assert flag.reason == "low_confidence"

    def test_ambiguous_creates_flag(self):
        decision = CorrectionDecision(
            original="dan",
            best="dẫn",
            best_score=0.90,
            second_best="dần",
            second_score=0.84,
            margin=0.06,
            decision=DecisionType.FLAG,
            reason="ambiguous_candidate",
        )
        flag = decision_to_flag(decision, token_index=1)
        assert flag is not None
        assert flag.span_text == "dan"
        assert flag.flag_type == FlagType.AMBIGUOUS_CANDIDATES
        assert flag.reason == "ambiguous_candidate"

    def test_need_context_creates_flag(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.90,
            second_best="bàn",
            second_score=0.75,
            margin=0.15,
            decision=DecisionType.NEED_CONTEXT,
            reason="needs_more_context",
        )
        flag = decision_to_flag(decision, token_index=2)
        assert flag is not None
        assert flag.span_text == "ban"
        assert flag.flag_type == FlagType.NO_SAFE_CORRECTION
        assert flag.reason == "needs_more_context"

    def test_accepted_returns_none(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.92,
            decision=DecisionType.ACCEPT,
            reason="accepted_high_confidence",
        )
        assert decision_to_flag(decision, token_index=0) is None

    def test_reject_returns_none(self):
        decision = CorrectionDecision(
            original="0987",
            best="0987",
            best_score=0.0,
            decision=DecisionType.REJECT,
            reason="protected_token",
        )
        assert decision_to_flag(decision, token_index=0) is None

    def test_flag_has_candidates(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.70,
            second_best="bàn",
            second_score=0.20,
            margin=0.50,
            decision=DecisionType.FLAG,
            reason="low_confidence",
        )
        flag = decision_to_flag(decision, token_index=0)
        assert flag is not None
        assert len(flag.candidates) == 1
        assert flag.candidates[0].text == "bán"
