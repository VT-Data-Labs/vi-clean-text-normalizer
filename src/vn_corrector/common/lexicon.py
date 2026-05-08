"""Lexicon domain types, store interface, and lookup results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from vn_corrector.common.enums import CandidateIndexSource, LexiconKind, LexiconSource
from vn_corrector.common.scoring import Score


@dataclass(frozen=True, slots=True)
class Provenance:
    source: LexiconSource = LexiconSource.BUILT_IN
    source_name: str | None = None
    version: str | None = None
    created_by: str | None = None
    note: str | None = None


# ── Lexicon entries ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LexiconEntry:
    entry_id: str
    surface: str
    normalized: str
    no_tone: str
    kind: LexiconKind = LexiconKind.WORD

    score: Score = field(default_factory=Score)
    provenance: Provenance = field(default_factory=Provenance)

    domain: str | None = None
    pos: str | None = None
    language: str = "vi"
    tags: tuple[str, ...] = field(default_factory=tuple)

    aliases: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.surface:
            raise ValueError("surface is required")
        if not self.normalized:
            raise ValueError("normalized is required")
        if not self.no_tone:
            raise ValueError("no_tone is required")
        self.score.validate()


@dataclass(frozen=True, slots=True)
class AbbreviationEntry:
    entry_id: str
    surface: str
    normalized: str
    expansions: tuple[str, ...]

    score: Score = field(default_factory=Score)
    provenance: Provenance = field(default_factory=Provenance)

    domain: str | None = None
    ambiguous: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.surface:
            raise ValueError("surface is required")
        if not self.normalized:
            raise ValueError("normalized is required")
        if not self.expansions:
            raise ValueError("expansions must not be empty")
        self.score.validate()


@dataclass(frozen=True, slots=True)
class PhraseEntry:
    entry_id: str
    phrase: str
    normalized: str
    no_tone: str
    n: int

    score: Score = field(default_factory=Score)
    provenance: Provenance = field(default_factory=Provenance)

    domain: str | None = None
    language: str = "vi"
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.phrase:
            raise ValueError("phrase is required")
        if not self.normalized:
            raise ValueError("normalized is required")
        if not self.no_tone:
            raise ValueError("no_tone is required")
        if self.n <= 0:
            raise ValueError("n must be > 0")
        self.score.validate()


@dataclass(frozen=True, slots=True)
class OcrConfusionEntry:
    entry_id: str
    noisy: str
    normalized_noisy: str
    corrections: tuple[str, ...]

    score: Score = field(default_factory=lambda: Score(confidence=0.7))
    provenance: Provenance = field(default_factory=Provenance)

    domain: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.noisy:
            raise ValueError("noisy is required")
        if not self.normalized_noisy:
            raise ValueError("normalized_noisy is required")
        if not self.corrections:
            raise ValueError("corrections must not be empty")
        self.score.validate()


LexiconRecord = LexiconEntry | AbbreviationEntry | PhraseEntry | OcrConfusionEntry


# ── Candidates and lookup results ──────────────────────────────────


@dataclass(frozen=True, slots=True)
class LexiconCandidate:
    text: str
    score: float
    source: CandidateIndexSource
    entry_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.text:
            raise ValueError("candidate.text is required")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("candidate.score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class LookupResult:
    query: str
    found: bool
    candidates: tuple[LexiconCandidate, ...] = field(default_factory=tuple)
    entries: tuple[LexiconRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OcrConfusionLookupResult:
    query: str
    found: bool
    corrections: tuple[LexiconCandidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LexiconLookupResult:
    query: str
    found: bool
    entries: tuple[LexiconEntry | AbbreviationEntry | PhraseEntry, ...] = field(
        default_factory=tuple
    )
    candidates: tuple[LexiconCandidate, ...] = field(default_factory=tuple)


# ── Store interface ────────────────────────────────────────────────


class LexiconStoreInterface(ABC):
    @abstractmethod
    def lookup(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_accentless(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_abbreviation(self, text: str) -> LexiconLookupResult: ...
    @abstractmethod
    def lookup_phrase(self, text: str) -> list[PhraseEntry]: ...
    @abstractmethod
    def lookup_phrase_str(self, text: str) -> str | None: ...
    @abstractmethod
    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]: ...
    @abstractmethod
    def lookup_ocr(self, text: str) -> list[str]: ...
    @abstractmethod
    def get_ocr_corrections(self, text: str) -> OcrConfusionLookupResult: ...
    @abstractmethod
    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]: ...
    @abstractmethod
    def contains_word(self, text: str) -> bool: ...
    @abstractmethod
    def contains_syllable(self, text: str) -> bool: ...
    @abstractmethod
    def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]: ...
    @abstractmethod
    def is_protected_token(self, text: str) -> bool: ...

    def query_prefix(self, _prefix: str) -> list[LexiconEntry] | None:
        return None
