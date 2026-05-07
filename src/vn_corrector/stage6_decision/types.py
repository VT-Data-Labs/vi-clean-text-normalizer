"""Re-exports and enums for M6 decision engine."""

from enum import StrEnum

from vn_corrector.common.types import (
    Candidate,
    ChangeReason,
    CorrectionChange,
    CorrectionDecision,
    CorrectionFlag,
    DecisionType,
    FlagType,
    TextSpan,
)
from vn_corrector.stage4_candidates.types import CandidateSource

__all__ = [
    "Candidate",
    "CandidateSource",
    "ChangeReason",
    "CorrectionChange",
    "CorrectionDecision",
    "CorrectionFlag",
    "DecisionReason",
    "DecisionType",
    "FlagType",
    "TextSpan",
]


class DecisionReason(StrEnum):
    """Stable reason codes for :attr:`CorrectionDecision.reason`."""

    NO_RANKED_SEQUENCE = "no_ranked_sequence"
    PROTECTED = "protected_token"
    NO_CANDIDATE = "no_candidate"
    IDENTITY = "identity_candidate"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS = "ambiguous_candidate"
    NEEDS_CONTEXT = "needs_more_context"
    ACCEPTED = "accepted_high_confidence"
