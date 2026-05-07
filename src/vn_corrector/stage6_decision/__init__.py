"""M6 — Decision Engine.

Deterministic safety layer that decides whether to accept, reject, or flag
each candidate correction based on confidence thresholds and margins.
"""

from vn_corrector.stage6_decision.changes import decision_to_change
from vn_corrector.stage6_decision.config import DecisionEngineConfig
from vn_corrector.stage6_decision.decision import DecisionEngine
from vn_corrector.stage6_decision.flags import decision_to_flag
from vn_corrector.stage6_decision.pipeline import decide_scored_window
from vn_corrector.stage6_decision.types import DecisionReason

__all__ = [
    "DecisionEngine",
    "DecisionEngineConfig",
    "DecisionReason",
    "decide_scored_window",
    "decision_to_change",
    "decision_to_flag",
]
