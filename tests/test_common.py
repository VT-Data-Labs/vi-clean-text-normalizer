"""Tests for common modules — constants, errors, types, validation."""

from vn_corrector.common.constants import (
    REPLACE_THRESHOLD,
    MIN_MARGIN,
    MAX_CANDIDATES_PER_TOKEN,
    UNICODE_NORMALIZATION_FORM,
)
from vn_corrector.common.errors import (
    CorrectionFlagType,
    DecisionType,
    CasePattern,
)
from vn_corrector.common.types import (
    CorrectionChange,
    CorrectionFlag,
    CorrectionResult,
    CorrectionDecision,
    CaseMask,
    Token,
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
    def test_correction_flag_type_values(self):
        assert CorrectionFlagType.AMBIGUOUS_DIACRITIC.value == "AMBIGUOUS_DIACRITIC"
        assert CorrectionFlagType.UNKNOWN_TOKEN.value == "UNKNOWN_TOKEN"

    def test_decision_type_values(self):
        assert DecisionType.REPLACE.value == "REPLACE"
        assert DecisionType.KEEP_ORIGINAL.value == "KEEP_ORIGINAL"
        assert DecisionType.FLAG_AMBIGUOUS.value == "FLAG_AMBIGUOUS"

    def test_case_pattern_values(self):
        assert CasePattern.UPPER.value == "UPPER"
        assert CasePattern.LOWER.value == "LOWER"
        assert CasePattern.TITLE.value == "TITLE"


class TestTypes:
    def test_correction_change_defaults(self):
        c = CorrectionChange("x", "y", 0, 1, 0.95, "test")
        assert not c.candidate_sources

    def test_correction_flag_defaults(self):
        f = CorrectionFlag("span", 0, 2, "AMBIGUOUS")
        assert not f.candidates
        assert f.reason == ""

    def test_correction_result_defaults(self):
        r = CorrectionResult("in", "out", 0.9)
        assert not r.changes
        assert not r.flags

    def test_case_mask_holds_pattern(self):
        m = CaseMask("RÓT", "rót", CasePattern.UPPER)
        assert m.original == "RÓT"
        assert m.case_pattern == CasePattern.UPPER

    def test_token_defaults(self):
        t = Token("hello", "FOREIGN_WORD")
        assert not t.protected

    def test_correction_decision_fields(self):
        d = CorrectionDecision(
            original="mùông",
            best="muỗng",
            best_score=0.93,
            second_best="mường",
            second_score=0.41,
            margin=0.52,
            decision=DecisionType.REPLACE,
        )
        assert d.decision == DecisionType.REPLACE
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
