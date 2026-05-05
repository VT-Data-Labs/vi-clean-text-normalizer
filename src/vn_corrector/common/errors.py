"""Correction flag types and error classes."""

from enum import Enum


class CorrectionFlagType(str, Enum):
    """Types of flags raised during correction."""

    AMBIGUOUS_DIACRITIC = "AMBIGUOUS_DIACRITIC"
    UNKNOWN_TOKEN = "UNKNOWN_TOKEN"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    PROTECTED_TOKEN = "PROTECTED_TOKEN"
    MIXED_LANGUAGE_SPAN = "MIXED_LANGUAGE_SPAN"
    POSSIBLE_LAYOUT_ERROR = "POSSIBLE_LAYOUT_ERROR"
    POSSIBLE_OCR_DESTRUCTION = "POSSIBLE_OCR_DESTRUCTION"
    DOMAIN_TERM_UNKNOWN = "DOMAIN_TERM_UNKNOWN"


class DecisionType(str, Enum):
    """Decision types for correction output."""

    KEEP_ORIGINAL = "KEEP_ORIGINAL"
    REPLACE = "REPLACE"
    FLAG_AMBIGUOUS = "FLAG_AMBIGUOUS"
    FLAG_UNKNOWN = "FLAG_UNKNOWN"
    PROTECTED = "PROTECTED"


class CasePattern(str, Enum):
    """Case pattern for a token (see Stage 2 — Case Masking)."""

    LOWER = "LOWER"
    UPPER = "UPPER"
    TITLE = "TITLE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"
