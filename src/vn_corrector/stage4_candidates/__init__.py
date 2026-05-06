"""Stage 4 — Candidate Generation.

Generates deterministic, bounded, explainable correction candidates
for Vietnamese OCR post-correction.

Public API
----------
- :class:`CandidateGenerator` — main orchestrator
- :class:`CandidateGeneratorConfig` — configuration
- :class:`Candidate`, :class:`CandidateSource`, :class:`CandidateEvidence` — types
- :class:`TokenCandidates`, :class:`CandidateDocument` — output containers
"""

from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig
from vn_corrector.stage4_candidates.generator import CandidateGenerator
from vn_corrector.stage4_candidates.types import (
    Candidate,
    CandidateDocument,
    CandidateEvidence,
    CandidateGenerationStats,
    CandidateSource,
    TokenCandidates,
)

__all__ = [
    "Candidate",
    "CandidateDocument",
    "CandidateEvidence",
    "CandidateGenerationStats",
    "CandidateGenerator",
    "CandidateGeneratorConfig",
    "CandidateSource",
    "TokenCandidates",
]
