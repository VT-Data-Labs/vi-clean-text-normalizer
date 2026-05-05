"""Tests for case masking (Stage 2 + Stage 8)."""

from vn_corrector.case_mask import (
    apply_case_mask,
    create_case_mask,
    detect_case_pattern,
    restore_case,
    to_lowercase,
    to_uppercase,
)
from vn_corrector.common.errors import CasePattern


class TestDetectCasePattern:
    def test_upper_vietnamese(self):
        assert detect_case_pattern("RỐT") == CasePattern.UPPER
        assert detect_case_pattern("NƯỚC") == CasePattern.UPPER

    def test_upper_multi_word(self):
        assert detect_case_pattern("RỐT NƯỚC") == CasePattern.UPPER

    def test_upper_with_dd(self):
        assert detect_case_pattern("ĐƯỜNG") == CasePattern.UPPER
        assert detect_case_pattern("LÊ LỢI") == CasePattern.UPPER

    def test_upper_with_mixed_english(self):
        assert detect_case_pattern("SỐ MÙÔNG") == CasePattern.UPPER

    def test_lower_vietnamese(self):
        assert detect_case_pattern("rốt") == CasePattern.LOWER
        assert detect_case_pattern("nước") == CasePattern.LOWER
        assert detect_case_pattern("đường") == CasePattern.LOWER

    def test_lower_multi_word(self):
        assert detect_case_pattern("rót nước") == CasePattern.LOWER

    def test_title_single_word(self):
        assert detect_case_pattern("Rót") == CasePattern.TITLE
        assert detect_case_pattern("Đường") == CasePattern.TITLE

    def test_title_vietnamese(self):
        assert detect_case_pattern("Rót Nước") == CasePattern.MIXED

    def test_title_english(self):
        assert detect_case_pattern("Hello") == CasePattern.TITLE

    def test_mixed_vietnamese(self):
        # "Rót nước" has first letter upper, rest lower → TITLE (not MIXED)
        assert detect_case_pattern("Rót nước") == CasePattern.TITLE

    def test_mixed_english(self):
        assert detect_case_pattern("iPhone") == CasePattern.MIXED
        assert detect_case_pattern("macOS") == CasePattern.MIXED

    def test_mixed_product_code(self):
        assert detect_case_pattern("SốMùÔng") == CasePattern.MIXED

    def test_empty_string(self):
        assert detect_case_pattern("") == CasePattern.UNKNOWN

    def test_no_alpha_chars(self):
        assert detect_case_pattern("123") == CasePattern.UNKNOWN
        assert detect_case_pattern("!@#") == CasePattern.UNKNOWN
        assert detect_case_pattern("  ") == CasePattern.UNKNOWN

    def test_single_char_upper(self):
        assert detect_case_pattern("A") == CasePattern.UPPER
        assert detect_case_pattern("Đ") == CasePattern.UPPER

    def test_single_char_lower(self):
        assert detect_case_pattern("a") == CasePattern.LOWER
        assert detect_case_pattern("đ") == CasePattern.LOWER

    def test_title_single_word_vietnamese(self):
        assert detect_case_pattern("Rót") == CasePattern.TITLE

    def test_mixed_with_numbers(self):
        assert detect_case_pattern("RỐT nước") == CasePattern.MIXED


class TestToLowercase:
    def test_vietnamese_upper_to_lower(self):
        assert to_lowercase("RỐT") == "rốt"
        assert to_lowercase("NƯỚC") == "nước"

    def test_vietnamese_dd(self):
        assert to_lowercase("Đ") == "đ"
        assert to_lowercase("ĐƯỜNG") == "đường"

    def test_vietnamese_title_to_lower(self):
        assert to_lowercase("Rót") == "rót"

    def test_english_to_lower(self):
        assert to_lowercase("HELLO") == "hello"
        assert to_lowercase("Hello") == "hello"

    def test_mixed_text(self):
        assert to_lowercase("RỐT NƯỚC") == "rốt nước"

    def test_empty_string(self):
        assert to_lowercase("") == ""

    def test_numbers_preserved(self):
        assert to_lowercase("RỐT 123") == "rốt 123"


class TestToUppercase:
    def test_vietnamese_lower_to_upper(self):
        assert to_uppercase("rốt") == "RỐT"
        assert to_uppercase("nước") == "NƯỚC"

    def test_vietnamese_dd(self):
        assert to_uppercase("đ") == "Đ"
        assert to_uppercase("đường") == "ĐƯỜNG"

    def test_vietnamese_title_to_upper(self):
        assert to_uppercase("Rót") == "RÓT"

    def test_english_to_upper(self):
        assert to_uppercase("hello") == "HELLO"

    def test_mixed_text(self):
        assert to_uppercase("rốt nước") == "RỐT NƯỚC"

    def test_empty_string(self):
        assert to_uppercase("") == ""


class TestRestoreCase:
    def test_restore_upper(self):
        assert restore_case("rót nước", CasePattern.UPPER) == "RÓT NƯỚC"

    def test_restore_lower(self):
        assert restore_case("RÓT NƯỚC", CasePattern.LOWER) == "rót nước"

    def test_restore_title(self):
        assert restore_case("rót", CasePattern.TITLE) == "Rót"

    def test_restore_title_vietnamese_dd(self):
        assert restore_case("đường", CasePattern.TITLE) == "Đường"

    def test_restore_unknown(self):
        assert restore_case("123", CasePattern.UNKNOWN) == "123"

    def test_restore_mixed_with_original(self):
        result = restore_case("rót nước", CasePattern.MIXED, original="Rót Nước")
        assert result == "Rót Nước"

    def test_restore_mixed_without_original(self):
        assert restore_case("rót nước", CasePattern.MIXED) == "rót nước"

    def test_restore_mixed_with_longer_working(self):
        result = restore_case("rót nước vào", CasePattern.MIXED, original="Rót")
        # Original: R(up) o(low) t(low) → working: r(up->up) ót...  actually:
        # r vs R (orig[0].isupper() → True) → w_ch.upper() = R
        # ó vs o (orig[1].isupper() → False) → w_ch.lower() = ó
        # t vs t (orig[2].isupper() → False) → w_ch.lower() = t
        # remaining chars: ' ', 'n', 'ư', 'ớ', 'c', ' ', 'v', 'à', 'o' → all lower
        assert result == "Rót nước vào"

    def test_empty_string(self):
        assert restore_case("", CasePattern.UPPER) == ""

    def test_single_char_upper(self):
        assert restore_case("r", CasePattern.UPPER) == "R"

    def test_single_char_lower(self):
        assert restore_case("R", CasePattern.LOWER) == "r"


class TestCreateCaseMask:
    def test_upper_mask(self):
        mask = create_case_mask("RỐT")
        assert mask.original == "RỐT"
        assert mask.working == "rốt"
        assert mask.case_pattern == CasePattern.UPPER

    def test_lower_mask(self):
        mask = create_case_mask("nước")
        assert mask.working == "nước"
        assert mask.case_pattern == CasePattern.LOWER

    def test_title_mask(self):
        mask = create_case_mask("Đường")
        assert mask.working == "đường"
        assert mask.case_pattern == CasePattern.TITLE

    def test_unknown_mask(self):
        mask = create_case_mask("123")
        assert mask.working == "123"
        assert mask.case_pattern == CasePattern.UNKNOWN

    def test_mixed_mask(self):
        mask = create_case_mask("Rót Nước")
        assert mask.working == "rót nước"
        assert mask.case_pattern == CasePattern.MIXED


class TestApplyCaseMask:
    def test_upper(self):
        mask = create_case_mask("RỐT")
        assert apply_case_mask("muỗng", mask) == "MUỖNG"

    def test_lower(self):
        mask = create_case_mask("nước")
        working = "nước"
        assert apply_case_mask(working, mask) == "nước"

    def test_title(self):
        mask = create_case_mask("Rót")
        assert apply_case_mask("rót", mask) == "Rót"

    def test_title_vietnamese_dd(self):
        mask = create_case_mask("Đường")
        assert apply_case_mask("đường", mask) == "Đường"

    def test_unknown(self):
        mask = create_case_mask("123")
        assert apply_case_mask("123", mask) == "123"

    def test_mixed_preserved(self):
        mask = create_case_mask("iPhone")
        assert apply_case_mask("iphone", mask) == "iPhone"

    def test_mixed_vietnamese_english(self):
        mask = create_case_mask("SốMùÔng")
        assert apply_case_mask("sốmùông", mask) == "SốMùÔng"


class TestVietnameseDdHandling:
    """Verify Đ/đ is handled correctly in all case operations."""

    def test_dd_detect_upper(self):
        assert detect_case_pattern("Đ") == CasePattern.UPPER
        assert detect_case_pattern("ĐẸP") == CasePattern.UPPER

    def test_dd_detect_lower(self):
        assert detect_case_pattern("đ") == CasePattern.LOWER
        assert detect_case_pattern("đẹp") == CasePattern.LOWER

    def test_dd_upper_to_lower(self):
        assert to_lowercase("ĐẸP") == "đẹp"
        assert to_lowercase("Đ") == "đ"

    def test_dd_lower_to_upper(self):
        assert to_uppercase("đẹp") == "ĐẸP"
        assert to_uppercase("đ") == "Đ"

    def test_dd_title_case(self):
        assert restore_case("đẹp", CasePattern.TITLE) == "Đẹp"

    def test_dd_in_mixed_restoration(self):
        # Original: ĐẹP → working: đẹp → restore MIXED
        # Đ(up) ẹ(low) P(up) → restored: Đ(up) ẹ(low) P(up) → "ĐẹP"
        result = restore_case("đẹp", CasePattern.MIXED, original="ĐẹP")
        assert result == "ĐẹP"
