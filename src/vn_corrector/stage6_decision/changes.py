from __future__ import annotations

from vn_corrector.common.correction import CorrectionChange, CorrectionDecision
from vn_corrector.common.enums import ChangeReason, DecisionType
from vn_corrector.common.spans import TextSpan
from vn_corrector.stage6_decision.types import DecisionReason


def decision_to_change(
    decision: CorrectionDecision,
    *,
    token_index: int,
    start: int | None = None,
    end: int | None = None,
) -> CorrectionChange | None:
    """Convert an accepted decision into a ``CorrectionChange``.

    Returns ``None`` when the decision is not ``ACCEPT`` or when
    the best candidate is identical to the original.
    """
    if decision.decision != DecisionType.ACCEPT:
        return None
    if decision.best is None:
        return None
    if decision.best == decision.original:
        return None

    reason = _reason_to_change_reason(decision.reason)
    span = TextSpan(
        start=start if start is not None else token_index,
        end=end if end is not None else token_index + 1,
    )

    return CorrectionChange(
        original=decision.original,
        replacement=decision.best,
        span=span,
        confidence=decision.best_score,
        reason=reason,
        decision=decision,
        candidate_sources=decision.candidate_sources,
    )


def _reason_to_change_reason(reason: str) -> ChangeReason:
    mapping: dict[str, ChangeReason] = {
        DecisionReason.ACCEPTED: ChangeReason.DIACRITIC_RESTORED,
    }
    return mapping.get(reason, ChangeReason.NORMALIZED)
