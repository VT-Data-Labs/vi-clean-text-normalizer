"""Backward-compatible re-exports — deprecated compatibility shim.

This module exists only so that existing ``from vn_corrector.common.types import X``
statements continue to work without changes.  New code should import directly
from the domain-specific submodule that owns the type:

=======================  =====================================================
Submodule                Types
=======================  =====================================================
``common.enums``         LexiconKind, LexiconSource, TokenType, FlagType,
                         DecisionReason, ChangeReason,     CandidateIndexSource,
                         CasePattern, DecisionType, SpanType
``common.spans``         TextSpan, ProtectedSpan, ProtectedDocument, Token,
                         CaseMask
``common.scoring``       Score, ScoreBreakdown
``common.correction``    CorrectionDecision, CorrectionChange, CorrectionFlag,
                         CorrectionResult
``common.contracts``     CandidateWindow, CandidateSequence, CorrectionEvidence,
                         MetadataValue, ScoredSequence, ScoredWindow,
                         TokenCorrectionExplanation
``lexicon.types``        Provenance, LexiconEntry, AbbreviationEntry,
                         PhraseEntry, OcrConfusionEntry, LexiconRecord,
                         LexiconCandidate, LookupResult, OcrConfusionLookupResult,
                         LexiconLookupResult
``lexicon.interface``    LexiconStoreInterface
=======================  =====================================================
"""

# ruff: noqa: F401  — re-exports for backward compat

from vn_corrector.common.contracts import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    MetadataValue,
    ScoredSequence,
    ScoredWindow,
    TokenCorrectionExplanation,
)
from vn_corrector.common.correction import (
    CorrectionChange,
    CorrectionDecision,
    CorrectionFlag,
    CorrectionResult,
)
from vn_corrector.common.enums import (
    CandidateIndexSource,
    CasePattern,
    ChangeReason,
    DecisionReason,
    DecisionType,
    FlagType,
    LexiconKind,
    LexiconSource,
    SpanType,
    TokenType,
)
from vn_corrector.common.scoring import Score, ScoreBreakdown
from vn_corrector.common.spans import CaseMask, ProtectedDocument, ProtectedSpan, TextSpan, Token
from vn_corrector.lexicon.interface import LexiconStoreInterface
from vn_corrector.lexicon.types import (
    AbbreviationEntry,
    LexiconCandidate,
    LexiconEntry,
    LexiconLookupResult,
    LexiconRecord,
    LookupResult,
    OcrConfusionEntry,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
)
