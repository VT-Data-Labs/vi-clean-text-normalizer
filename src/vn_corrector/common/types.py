"""Core production data types for the Vietnamese correction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

# ---------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------


class LexiconKind(StrEnum):
    SYLLABLE = "syllable"
    WORD = "word"
    PHRASE = "phrase"
    UNIT = "unit"
    NAME = "name"
    LOCATION = "location"
    BRAND = "brand"
    ABBREVIATION = "abbreviation"
    DOMAIN_TERM = "domain_term"


class LexiconSource(StrEnum):
    BUILT_IN = "built-in"
    MANUAL = "manual"
    CORPUS = "corpus"
    OCR_REVIEW = "ocr-review"
    USER_FEEDBACK = "user-feedback"
    EXTERNAL_DICTIONARY = "external-dictionary"


class TokenType(StrEnum):
    VI_WORD = "VI_WORD"
    FOREIGN_WORD = "FOREIGN_WORD"
    NUMBER = "NUMBER"
    UNIT = "UNIT"
    PUNCT = "PUNCT"
    SPACE = "SPACE"
    NEWLINE = "NEWLINE"
    PROTECTED = "PROTECTED"
    UNKNOWN = "UNKNOWN"


class FlagType(StrEnum):
    UNKNOWN_TOKEN = "unknown_token"
    AMBIGUOUS_CANDIDATES = "ambiguous_candidates"
    LOW_CONFIDENCE = "low_confidence"
    OCR_SUSPECT = "ocr_suspect"
    CASE_RESTORATION_FAILED = "case_restoration_failed"
    DOMAIN_CONFLICT = "domain_conflict"
    NO_SAFE_CORRECTION = "no_safe_correction"


class ChangeReason(StrEnum):
    DIACRITIC_RESTORED = "diacritic_restored"
    OCR_CONFUSION_FIXED = "ocr_confusion_fixed"
    ABBREVIATION_EXPANDED = "abbreviation_expanded"
    CASE_RESTORED = "case_restored"
    NORMALIZED = "normalized"
    PHRASE_CORRECTED = "phrase_corrected"
    DOMAIN_CANONICALIZED = "domain_canonicalized"


class CandidateSource(StrEnum):
    SURFACE_INDEX = "surface_index"
    NO_TONE_INDEX = "no_tone_index"
    PHRASE_INDEX = "phrase_index"
    OCR_CONFUSION_INDEX = "ocr_confusion_index"
    ABBREVIATION_INDEX = "abbreviation_index"
    LANGUAGE_MODEL = "language_model"
    RULE = "rule"


class CasePattern(StrEnum):
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DecisionType(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    FLAG = "flag"
    NEED_CONTEXT = "need_context"


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Character span in the original input text."""

    start: int
    end: int

    def validate(self) -> None:
        if self.start < 0:
            raise ValueError("span.start must be >= 0")
        if self.end < self.start:
            raise ValueError("span.end must be >= span.start")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where an entry or correction came from."""

    source: LexiconSource = LexiconSource.BUILT_IN
    source_name: str | None = None
    version: str | None = None
    created_by: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Score:
    """Common scoring object."""

    confidence: float = 1.0
    frequency: float = 0.0
    priority: int = 0

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.frequency < 0:
            raise ValueError("frequency must be >= 0")


# ---------------------------------------------------------------------
# Lexicon entries
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LexiconEntry:
    """
    A canonical lexicon entry.

    Example:
        surface="muỗng"
        normalized="muỗng"
        no_tone="muong"
        kind=LexiconKind.WORD
    """

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
    """
    Abbreviation entry.

    Example:
        surface="q."
        expansions=("quận",)
    """

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
    """
    Multi-token phrase entry.

    Example:
        phrase="số muỗng"
        no_tone="so muong"
        n=2
    """

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
    """
    OCR confusion mapping.

    Example:
        noisy="mùông"
        corrections=("muỗng",)
    """

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


# ---------------------------------------------------------------------
# Lookup results
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Candidate:
    """A correction candidate returned from any index."""

    text: str
    score: float
    source: CandidateSource
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
    """Generic lookup result."""

    query: str
    found: bool
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)
    entries: tuple[LexiconRecord, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OcrConfusionLookupResult:
    """Result of an OCR confusion lookup."""

    query: str
    found: bool
    corrections: tuple[Candidate, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LexiconLookupResult:
    """Result of a lexicon lookup."""

    query: str
    found: bool
    entries: tuple[LexiconEntry | AbbreviationEntry | PhraseEntry, ...] = field(
        default_factory=tuple
    )
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------
# Tokenization / case masking
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CaseMask:
    """Case pattern for a token."""

    original: str
    working: str
    case_pattern: CasePattern
    uppercase_positions: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class Token:
    """A single token from the tokenizer."""

    text: str
    token_type: TokenType
    span: TextSpan
    normalized: str | None = None
    no_tone: str | None = None
    protected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.text == "":
            raise ValueError("token.text must not be empty")
        self.span.validate()


# ---------------------------------------------------------------------
# Correction output
# ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorrectionDecision:
    """Decision metadata for a single corrected span."""

    original: str
    best: str | None
    best_score: float
    second_best: str | None = None
    second_score: float = 0.0
    margin: float = 0.0
    decision: DecisionType = DecisionType.FLAG
    reason: str = ""
    candidate_sources: tuple[CandidateSource, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if not 0.0 <= self.best_score <= 1.0:
            raise ValueError("best_score must be between 0 and 1")
        if not 0.0 <= self.second_score <= 1.0:
            raise ValueError("second_score must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class CorrectionChange:
    """A single applied correction."""

    original: str
    replacement: str
    span: TextSpan
    confidence: float
    reason: ChangeReason
    decision: CorrectionDecision | None = None
    candidate_sources: tuple[CandidateSource, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        if self.original == "":
            raise ValueError("original must not be empty")
        if self.replacement == "":
            raise ValueError("replacement must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        self.span.validate()


@dataclass(frozen=True, slots=True)
class CorrectionFlag:
    """A flag raised during correction."""

    span_text: str
    span: TextSpan
    flag_type: FlagType
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)
    reason: str = ""
    severity: Literal["info", "warning", "error"] = "warning"

    def validate(self) -> None:
        if self.span_text == "":
            raise ValueError("span_text must not be empty")
        self.span.validate()


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    """Full output of a correction pass."""

    original_text: str
    corrected_text: str
    confidence: float
    changes: tuple[CorrectionChange, ...] = field(default_factory=tuple)
    flags: tuple[CorrectionFlag, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
