"""Core types for Stage 4 — Candidate Generation.

Defines the candidate representation, evidence tracking, source enumeration,
and structured output types used throughout the candidate generation pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from vn_corrector.common.types import (
    AbbreviationEntry,
    LexiconEntry,
    PhraseEntry,
    Token,
    TokenType,
)

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
    metadata: Mapping[str, object] = field(default_factory=dict)


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
# Protocol types for duck-typed config/lexicon
# ---------------------------------------------------------------------------


class LexiconLookupResult(Protocol):
    """Result of ``lookup_accentless``."""

    entries: list[LexiconEntry | AbbreviationEntry]


class OcrCorrectionResult(Protocol):
    """Result of ``get_ocr_corrections``."""

    corrections: tuple[str, ...]


class LexiconAbbreviationResult(Protocol):
    """Result of ``lookup_abbreviation``."""

    entries: list[AbbreviationEntry]


class LexiconStoreProtocol(Protocol):
    """Duck-typed protocol for the lexicon store used by source generators."""

    def get_syllable_candidates(self, no_tone: str) -> Iterable[LexiconEntry]: ...
    def lookup_accentless(self, no_tone: str) -> LexiconLookupResult | None: ...
    def lookup_ocr(self, text: str) -> Iterable[str] | None: ...
    def get_ocr_corrections(self, text: str) -> OcrCorrectionResult: ...
    def lookup_abbreviation(self, text: str) -> LexiconAbbreviationResult | None: ...
    def query_prefix(self, prefix: str) -> Iterable[LexiconEntry | AbbreviationEntry] | None: ...
    def lookup_phrase_str(self, raw_phrase: str) -> object | None: ...
    def lookup_phrase(self, raw_phrase: str) -> list[PhraseEntry] | None: ...
    def lookup_phrase_normalized(self, key: str) -> list[PhraseEntry] | None: ...


class CandidateGeneratorConfigProtocol(Protocol):
    """Duck-typed protocol for generator configuration."""

    @property
    def enable_original(self) -> bool: ...
    @property
    def enable_ocr_confusion(self) -> bool: ...
    @property
    def enable_syllable_map(self) -> bool: ...
    @property
    def enable_word_lexicon(self) -> bool: ...
    @property
    def enable_abbreviation(self) -> bool: ...
    @property
    def enable_phrase_evidence(self) -> bool: ...
    @property
    def enable_domain_specific(self) -> bool: ...
    @property
    def enable_edit_distance(self) -> bool: ...
    @property
    def max_candidates_per_token(self) -> int: ...
    @property
    def max_ocr_replacements_per_token(self) -> int: ...
    @property
    def max_edit_distance(self) -> int: ...
    @property
    def deterministic_sort(self) -> bool: ...
    @property
    def keep_original_first(self) -> bool: ...
    @property
    def max_phrase_window(self) -> int: ...
    @property
    def min_token_length_for_edit_distance(self) -> int: ...
    @property
    def max_token_length_for_edit_distance(self) -> int: ...
    @property
    def enable_diagnostics(self) -> bool: ...
    @property
    def source_prior_weights(self) -> dict[str, float]: ...
    @property
    def identity_token_types(self) -> tuple[str, ...]: ...
    @property
    def candidate_token_types(self) -> tuple[str, ...]: ...
    @property
    def skip_non_word_tokens(self) -> bool: ...
    @property
    def cache_enabled(self) -> bool: ...


# ---------------------------------------------------------------------------
# Internal helper for source generators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateRequest:
    """Immutable request passed to each source generator."""

    token_text: str
    token_index: int | None = None
    token_type: TokenType | None = None
    protected: bool = False


@dataclass(frozen=True)
class CandidateContext:
    """Immutable context passed to each source generator."""

    tokens: Sequence[Token] | None
    lexicon: LexiconStoreProtocol
    config: CandidateGeneratorConfigProtocol


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
    "CandidateGeneratorConfigProtocol",
    "CandidateProposal",
    "CandidateRequest",
    "CandidateSource",
    "LexiconAbbreviationResult",
    "LexiconLookupResult",
    "LexiconStoreProtocol",
    "OcrCorrectionResult",
    "TokenCandidates",
]
