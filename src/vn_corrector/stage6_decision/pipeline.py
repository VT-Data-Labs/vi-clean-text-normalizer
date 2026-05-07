from __future__ import annotations

from vn_corrector.common.contracts import ScoredWindow
from vn_corrector.common.correction import CorrectionChange, CorrectionDecision, CorrectionFlag
from vn_corrector.stage6_decision.changes import decision_to_change
from vn_corrector.stage6_decision.config import DecisionEngineConfig
from vn_corrector.stage6_decision.decision import DecisionEngine
from vn_corrector.stage6_decision.flags import decision_to_flag


def decide_scored_window(
    scored_window: ScoredWindow,
    *,
    config: DecisionEngineConfig | None = None,
) -> tuple[
    list[CorrectionDecision],
    list[CorrectionChange],
    list[CorrectionFlag],
]:
    """Run the full M6 decision pipeline over one scored window.

    Returns ``(decisions, changes, flags)``.
    """
    engine = DecisionEngine(config)
    decisions = engine.decide_window(scored_window)

    changes: list[CorrectionChange] = []
    flags: list[CorrectionFlag] = []

    for i, decision in enumerate(decisions):
        tc = scored_window.window.token_candidates[i]

        change = decision_to_change(
            decision,
            token_index=tc.token_index,
        )
        if change is not None:
            changes.append(change)

        flag = decision_to_flag(
            decision,
            token_index=tc.token_index,
        )
        if flag is not None:
            flags.append(flag)

    return decisions, changes, flags
