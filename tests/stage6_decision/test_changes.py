"""Tests for M6 change builder — decision_to_change."""

from vn_corrector.common.correction import CorrectionDecision
from vn_corrector.common.enums import ChangeReason, DecisionType
from vn_corrector.stage6_decision.changes import decision_to_change


class TestDecisionToChange:
    def test_accepted_produces_change(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.92,
            second_best="bàn",
            second_score=0.60,
            margin=0.32,
            decision=DecisionType.ACCEPT,
            reason="accepted_high_confidence",
        )
        change = decision_to_change(decision, token_index=1)
        assert change is not None
        assert change.original == "ban"
        assert change.replacement == "bán"
        assert change.confidence == 0.92
        assert change.reason == ChangeReason.DIACRITIC_RESTORED

    def test_reject_returns_none(self):
        decision = CorrectionDecision(
            original="ban",
            best="ban",
            best_score=0.0,
            decision=DecisionType.REJECT,
            reason="identity_candidate",
        )
        assert decision_to_change(decision, token_index=0) is None

    def test_flag_returns_none(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.70,
            decision=DecisionType.FLAG,
            reason="low_confidence",
        )
        assert decision_to_change(decision, token_index=0) is None

    def test_need_context_returns_none(self):
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
        assert decision_to_change(decision, token_index=0) is None

    def test_best_none_returns_none(self):
        decision = CorrectionDecision(
            original="ban",
            best=None,
            best_score=0.0,
            decision=DecisionType.REJECT,
            reason="no_candidate",
        )
        assert decision_to_change(decision, token_index=0) is None

    def test_identity_returns_none(self):
        decision = CorrectionDecision(
            original="nhà",
            best="nhà",
            best_score=0.90,
            decision=DecisionType.REJECT,
            reason="identity_candidate",
        )
        assert decision_to_change(decision, token_index=0) is None

    def test_change_carries_decision(self):
        decision = CorrectionDecision(
            original="ban",
            best="bán",
            best_score=0.92,
            decision=DecisionType.ACCEPT,
            reason="accepted_high_confidence",
        )
        change = decision_to_change(decision, token_index=2)
        assert change is not None
        assert change.decision is decision
