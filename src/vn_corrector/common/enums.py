"""Pipeline-wide enums used by all stages.

Every enum here is a :class:`StrEnum` so values are JSON-serialisable and
comparable to plain strings.  Enums are grouped by concern below.

Consumed by
-----------
*All stages* — these are the lowest-level shared constants in the project.
``common/spans.py``, ``common/correction.py``, ``common/contracts.py``,
``lexicon/types.py``, and ``lexicon/interface.py`` all import from here.

Stage conventions
-----------------
+------------------+----------------------------------------------------+
| Stage            | Enums used                                         |
+==================+====================================================+
| 0/1 Normalise    | ``TokenType``, ``CasePattern``                     |
+------------------+----------------------------------------------------+
| 2 Lexicon        | ``LexiconKind``, ``LexiconSource``                 |
+------------------+----------------------------------------------------+
| 3 Protect        | ``SpanType``                                       |
+------------------+----------------------------------------------------+
| 4 Candidates     | ``CandidateSource``, ``TokenType``                 |
+------------------+----------------------------------------------------+
| 5 Scorer         | *(none directly; uses types that embed these)*     |
+------------------+----------------------------------------------------+
| 6 Decision       | ``DecisionReason``, ``DecisionType``,              |
|                  | ``FlagType``, ``ChangeReason``, ``CandidateIndexSource``|
+------------------+----------------------------------------------------+
"""

from __future__ import annotations

from enum import StrEnum


class LexiconKind(StrEnum):
    """Categories of entries stored in the lexicon.

    Used by ``lexicon/types.py`` (:class:`~vn_corrector.lexicon.types.LexiconEntry`)
    and all Stage-2 builders to classify dictionary entries.
    """

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
    """Provenance tags for where a lexicon entry originated.

    Used by ``lexicon/types.py`` (:class:`~vn_corrector.lexicon.types.Provenance`)
    and ``lexicon/interface.py``.
    """

    BUILT_IN = "built-in"
    MANUAL = "manual"
    CORPUS = "corpus"
    OCR_REVIEW = "ocr-review"
    USER_FEEDBACK = "user-feedback"
    EXTERNAL_DICTIONARY = "external-dictionary"


class TokenType(StrEnum):
    """Classifications assigned by the tokenizer (:mod:`vn_corrector.tokenizer`).

    Consumed by ``common/spans.py`` (:class:`~vn_corrector.common.spans.Token`),
    Stage-4 generators, and Stage-6 decision logic.
    """

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
    """Warning categories raised during correction.

    Each flag is attached to a :class:`~vn_corrector.common.correction.CorrectionFlag`
    in the Stage-6 decision layer.  Consumers (CLI, API) use these to decide
    whether to surface a warning to the user.
    """

    UNKNOWN_TOKEN = "unknown_token"
    AMBIGUOUS_CANDIDATES = "ambiguous_candidates"
    LOW_CONFIDENCE = "low_confidence"
    OCR_SUSPECT = "ocr_suspect"
    CASE_RESTORATION_FAILED = "case_restoration_failed"
    DOMAIN_CONFLICT = "domain_conflict"
    NO_SAFE_CORRECTION = "no_safe_correction"


class DecisionReason(StrEnum):
    """Stable reason codes for :attr:`~vn_corrector.common.correction.CorrectionDecision.reason`.

    Produced by the Stage-6 :class:`~vn_corrector.stage6_decision.decision.DecisionEngine`
    and consumed by callers (CLI, API) to understand *why* a token was
    accepted, rejected, or flagged.
    """

    NO_RANKED_SEQUENCE = "no_ranked_sequence"
    PROTECTED = "protected_token"
    NO_CANDIDATE = "no_candidate"
    IDENTITY = "identity_candidate"
    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS = "ambiguous_candidate"
    NEEDS_CONTEXT = "needs_more_context"
    ACCEPTED = "accepted_high_confidence"


class ChangeReason(StrEnum):
    """Explanatory tags for a :class:`~vn_corrector.common.correction.CorrectionChange`.

    Each value describes *what kind of correction* was applied so that
    consumers can filter, group, or explain changes to end users.
    """

    DIACRITIC_RESTORED = "diacritic_restored"
    OCR_CONFUSION_FIXED = "ocr_confusion_fixed"
    ABBREVIATION_EXPANDED = "abbreviation_expanded"
    CASE_RESTORED = "case_restored"
    NORMALIZED = "normalized"
    PHRASE_CORRECTED = "phrase_corrected"
    DOMAIN_CANONICALIZED = "domain_canonicalized"


class CandidateIndexSource(StrEnum):
    """Identifies which index service produced a
    :class:`~vn_corrector.lexicon.types.LexiconCandidate`.

    Used by lexicon backends to tag their output and by Stage-6 decision
    logic to weight or explain candidate provenance.
    """

    SURFACE_INDEX = "surface_index"
    NO_TONE_INDEX = "no_tone_index"
    PHRASE_INDEX = "phrase_index"
    OCR_CONFUSION_INDEX = "ocr_confusion_index"
    ABBREVIATION_INDEX = "abbreviation_index"
    LANGUAGE_MODEL = "language_model"
    RULE = "rule"


class CasePattern(StrEnum):
    """Case-mask patterns detected by :mod:`vn_corrector.case_mask`.

    Determines how a :class:`~vn_corrector.common.spans.CaseMask` token
    should be restored after the working (lowercase) correction pass.
    """

    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DecisionType(StrEnum):
    """Top-level decision outcomes for a corrected token.

    Produced by the Stage-6 :class:`~vn_corrector.stage6_decision.decision.DecisionEngine`
    and embedded in :class:`~vn_corrector.common.correction.CorrectionDecision`.
    """

    ACCEPT = "accept"
    REJECT = "reject"
    FLAG = "flag"
    NEED_CONTEXT = "need_context"


class SpanType(StrEnum):
    """Types of protected spans detected by Stage-3 matchers.

    Each :class:`~vn_corrector.common.spans.ProtectedSpan` carries one of
    these to identify what kind of content was masked (URL, email, price, etc.).
    """

    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    NUMBER = "number"
    UNIT = "unit"
    MONEY = "money"
    PERCENT = "percent"
    CODE = "code"
    DATE = "date"
