"""Core data types for the correction pipeline."""

from dataclasses import dataclass, field

from vn_corrector.common.errors import CasePattern, DecisionType


@dataclass
class LexiconEntry:
    """A single lexicon entry (syllable, word, or unit)."""

    surface: str
    normalized: str
    no_tone: str = ""
    kind: str = "word"
    source: str = "built-in"
    confidence: float = 1.0
    frequency: float = 0.0
    domain: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class AbbreviationEntry:
    """A single abbreviation with its expansions."""

    surface: str
    normalized: str
    expansions: list[str]
    source: str = "built-in"
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    domain: str | None = None
    ambiguous: bool = False


@dataclass
class LexiconLookupResult:
    """Result of a lexicon lookup."""

    found: bool
    entries: list[LexiconEntry | AbbreviationEntry] = field(default_factory=list)


@dataclass
class CorrectionChange:
    """A single applied correction."""

    original: str
    replacement: str
    start: int
    end: int
    confidence: float
    reason: str
    candidate_sources: list[str] = field(default_factory=list)


@dataclass
class CorrectionFlag:
    """A flag raised during correction (ambiguous, unknown, etc.)."""

    span: str
    start: int
    end: int
    type: str
    candidates: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class CorrectionResult:
    """Full output of a correction pass."""

    original_text: str
    corrected_text: str
    confidence: float
    changes: list[CorrectionChange] = field(default_factory=list)
    flags: list[CorrectionFlag] = field(default_factory=list)


@dataclass
class CaseMask:
    """Case pattern for a token."""

    original: str
    working: str
    case_pattern: CasePattern


@dataclass
class Token:
    """A single token from the tokenizer."""

    text: str
    token_type: (
        str  # VI_WORD, FOREIGN_WORD, NUMBER, UNIT, PUNCT, SPACE, NEWLINE, PROTECTED, UNKNOWN
    )
    protected: bool = False


@dataclass
class CorrectionDecision:
    """Decision metadata for a single corrected span."""

    original: str
    best: str
    best_score: float
    second_best: str
    second_score: float
    margin: float
    decision: DecisionType
