"""Tests for common modules — constants, errors, types, validation."""

from vn_corrector.common.constants import (
    MAX_CANDIDATES_PER_TOKEN,
    MIN_MARGIN,
    REPLACE_THRESHOLD,
    UNICODE_NORMALIZATION_FORM,
)
from vn_corrector.common.types import (
    CaseMask,
    CasePattern,
    ChangeReason,
    CorrectionChange,
    CorrectionDecision,
    CorrectionFlag,
    CorrectionResult,
    DecisionType,
    FlagType,
    TextSpan,
    Token,
    TokenType,
)
from vn_corrector.common.validation import is_nonempty_string, is_probability


class TestConstants:
    def test_thresholds_are_reasonable(self):
        assert 0.0 < REPLACE_THRESHOLD < 1.0
        assert 0.0 < MIN_MARGIN < 1.0

    def test_candidate_limits_positive(self):
        assert MAX_CANDIDATES_PER_TOKEN > 0
        assert UNICODE_NORMALIZATION_FORM == "NFC"


class TestErrorEnums:
    def test_flag_type_values(self):
        assert FlagType.UNKNOWN_TOKEN.value == "unknown_token"
        assert FlagType.AMBIGUOUS_CANDIDATES.value == "ambiguous_candidates"

    def test_decision_type_values(self):
        assert DecisionType.ACCEPT.value == "accept"
        assert DecisionType.REJECT.value == "reject"
        assert DecisionType.FLAG.value == "flag"

    def test_case_pattern_values(self):
        assert CasePattern.UPPER.value == "upper"
        assert CasePattern.LOWER.value == "lower"
        assert CasePattern.TITLE.value == "title"


class TestTypes:
    def test_correction_change_defaults(self):
        c = CorrectionChange(
            original="x",
            replacement="y",
            span=TextSpan(start=0, end=1),
            confidence=0.95,
            reason=ChangeReason.DIACRITIC_RESTORED,
        )
        assert not c.candidate_sources

    def test_correction_flag_defaults(self):
        f = CorrectionFlag(
            span_text="span",
            span=TextSpan(start=0, end=2),
            flag_type=FlagType.AMBIGUOUS_CANDIDATES,
        )
        assert not f.candidates
        assert f.reason == ""

    def test_correction_result_defaults(self):
        r = CorrectionResult(original_text="in", corrected_text="out", confidence=0.9)
        assert not r.changes
        assert not r.flags

    def test_case_mask_holds_pattern(self):
        m = CaseMask(original="RÓT", working="rót", case_pattern=CasePattern.UPPER)
        assert m.original == "RÓT"
        assert m.case_pattern == CasePattern.UPPER

    def test_token_defaults(self):
        t = Token(text="hello", token_type=TokenType.FOREIGN_WORD, span=TextSpan(start=0, end=5))
        assert not t.protected

    def test_correction_decision_fields(self):
        d = CorrectionDecision(
            original="mùông",
            best="muỗng",
            best_score=0.93,
            second_best="mường",
            second_score=0.41,
            margin=0.52,
            decision=DecisionType.ACCEPT,
        )
        assert d.decision == DecisionType.ACCEPT
        assert d.margin == 0.52


class TestValidation:
    def test_is_nonempty_string(self):
        assert is_nonempty_string("hello")
        assert not is_nonempty_string("")
        assert not is_nonempty_string(None)
        assert not is_nonempty_string(123)

    def test_is_probability(self):
        assert is_probability(0.0)
        assert is_probability(0.5)
        assert is_probability(1.0)
        assert not is_probability(-0.1)
        assert not is_probability(1.1)
        assert not is_probability("0.5")
