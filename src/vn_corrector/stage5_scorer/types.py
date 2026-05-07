"""Core types for the M5 phrase scorer — re-exported from common.

All shared pipeline types now live in :mod:`vn_corrector.common.types`.
Only M5-internal types remain here.
"""

from vn_corrector.common.contracts import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    MetadataValue,
    ScoredSequence,
    ScoredWindow,
    TokenCorrectionExplanation,
)
from vn_corrector.common.scoring import ScoreBreakdown

__all__ = [
    "CandidateSequence",
    "CandidateWindow",
    "CorrectionEvidence",
    "MetadataValue",
    "ScoreBreakdown",
    "ScoredSequence",
    "ScoredWindow",
    "TokenCorrectionExplanation",
]
