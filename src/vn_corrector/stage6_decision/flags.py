from __future__ import annotations

from vn_corrector.common.types import (
    Candidate,
    CandidateSource,
    CorrectionFlag,
    FlagType,
    TextSpan,
)
from vn_corrector.stage6_decision.types import (
    CorrectionDecision,
    DecisionReason,
    DecisionType,
)


def decision_to_flag(
    decision: CorrectionDecision,
    *,
    token_index: int,
    start: int | None = None,
    end: int | None = None,
) -> CorrectionFlag | None:
    """Convert a non-accepted decision into a ``CorrectionFlag``.

    Returns ``None`` for ``ACCEPT`` and ``REJECT`` decisions.
    Only ``FLAG`` and ``NEED_CONTEXT`` produce flags.
    """
    if decision.decision == DecisionType.ACCEPT:
        return None
    if decision.decision == DecisionType.REJECT:
        return None

    flag_type = _reason_to_flag_type(decision.reason)
    candidates: tuple[Candidate, ...] = ()
    if decision.best is not None:
        candidates = (
            Candidate(
                text=decision.best,
                score=decision.best_score,
                source=CandidateSource.NO_TONE_INDEX,
                reason=decision.reason,
            ),
        )

    span = TextSpan(
        start=start if start is not None else token_index,
        end=end if end is not None else token_index + 1,
    )

    return CorrectionFlag(
        span_text=decision.original,
        span=span,
        flag_type=flag_type,
        candidates=candidates,
        reason=decision.reason,
    )


def _reason_to_flag_type(reason: str) -> FlagType:
    mapping: dict[str, FlagType] = {
        DecisionReason.LOW_CONFIDENCE: FlagType.LOW_CONFIDENCE,
        DecisionReason.AMBIGUOUS: FlagType.AMBIGUOUS_CANDIDATES,
        DecisionReason.NEEDS_CONTEXT: FlagType.NO_SAFE_CORRECTION,
    }
    return mapping.get(reason, FlagType.UNKNOWN_TOKEN)
