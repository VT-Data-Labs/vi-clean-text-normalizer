"""Core types for Stage 4 — Candidate Generation.

Defines the candidate representation, evidence tracking, source enumeration,
and structured output types used throughout the candidate generation pipeline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from vn_corrector.common.types import (
    LexiconStoreInterface,
    Token,
    TokenType,
)
from vn_corrector.stage4_candidates.config import CandidateGeneratorConfig

MetadataValue = str | int | float | bool | None

# ---------------------------------------------------------------------------
# Candidate source enumeration
# ---------------------------------------------------------------------------


class CandidateSource(StrEnum):
    """Provenance categories for candidate generation."""

    ORIGINAL = "original"
    OCR_CONFUSION = "ocr_confusion"
    SYLLABLE_MAP = "syllable_map"
    WORD_LEXICON = "word_lexicon"
    ABBREVIATION = "abbreviation"
    PHRASE_SPECIFIC = "phrase_specific"
    DOMAIN_SPECIFIC = "domain_specific"
    EDIT_DISTANCE = "edit_distance"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateEvidence:
    """A single piece of evidence explaining why a candidate was generated."""

    source: CandidateSource
    detail: str
    confidence_hint: float = 0.0
    matched_text: str | None = None
    matched_key: str | None = None
    metadata: Mapping[str, MetadataValue] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """A single correction candidate with full provenance."""

    text: str
    normalized: str
    no_tone_key: str
    sources: set[CandidateSource]
    evidence: list[CandidateEvidence]
    prior_score: float = 0.0
    lexicon_freq: float = 0.0
    edit_distance: int | None = None
    is_original: bool = False
    replacement_token_count: int = 1


# ---------------------------------------------------------------------------
# Per-token wrapper
# ---------------------------------------------------------------------------


@dataclass
class TokenCandidates:
    """Candidates generated for a single token position."""

    token_text: str
    token_index: int
    protected: bool
    candidates: list[Candidate]
    diagnostics: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Document-level output
# ---------------------------------------------------------------------------


@dataclass
class CandidateGenerationStats:
    """Aggregate statistics for a document-level generation pass."""

    total_tokens: int = 0
    protected_tokens: int = 0
    skipped_tokens: int = 0
    generated_tokens: int = 0
    total_candidates: int = 0
    avg_candidates_per_token: float = 0.0
    max_candidates_seen: int = 0
    trimmed_tokens: int = 0
    cache_hits: int = 0


@dataclass
class CandidateDocument:
    """Complete candidate generation result for a document."""

    token_candidates: list[TokenCandidates]
    stats: CandidateGenerationStats


# ---------------------------------------------------------------------------
# Context types passed to source generators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateRequest:
    """Immutable request passed to each source generator."""

    token_text: str
    token_index: int | None = None
    token_type: TokenType | None = None
    protected: bool = False


@dataclass
class CandidateContext:
    """Context passed to each source generator.

    The ``tokens`` and ``candidate_texts`` fields are populated by the
    generator after initial source passes so that PhraseEvidenceSource
    can inspect all variation texts.
    """

    tokens: Sequence[Token] | None
    lexicon: LexiconStoreInterface
    config: CandidateGeneratorConfig
    candidate_texts: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class CandidateProposal:
    """A raw proposal from a single source before merging/ranking."""

    text: str
    source: CandidateSource
    evidence: CandidateEvidence
    prior_score: float = 0.0
    edit_distance: int | None = None

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("CandidateProposal text must not be empty")


__all__ = [
    "Candidate",
    "CandidateContext",
    "CandidateDocument",
    "CandidateEvidence",
    "CandidateGenerationStats",
    "CandidateProposal",
    "CandidateRequest",
    "CandidateSource",
    "MetadataValue",
    "TokenCandidates",
]
