"""Tests for the Unicode normalizer (Stage 0 + Stage 1)."""

import unicodedata

import pytest

from vn_corrector.normalizer import (
    normalize,
    normalize_unicode,
    normalize_whitespace,
    remove_invisible_characters,
)


class TestNormalizeUnicode:
    def test_nfc_preserves_already_normalized(self):
        text = "RÓT NƯỚC VÀO DỤNG CỤ"
        assert normalize_unicode(text) == text

    def test_nfd_to_nfc_conversion(self):
        # 'RÓT' in NFD form using combining marks
        r_acute_nfd = "R" + "́"  # R + combining acute
        o_circ_acute_nfd = "O" + "̂" + "́"  # O + circumflex + acute
        t = "T"
        nfd_text = r_acute_nfd + o_circ_acute_nfd + t
        result = normalize_unicode(nfd_text)
        # NFC should have single codepoints
        assert len(result) < len(nfd_text)
        assert unicodedata.is_normalized("NFC", result)

    def test_vietnamese_dd_preserved(self):
        assert normalize_unicode("Đường") == "Đường"
        assert normalize_unicode("đ") == "đ"

    def test_empty_string(self):
        assert normalize_unicode("") == ""

    def test_mixed_scripts(self):
        text = "DHA, ARA, số lượng"
        result = normalize_unicode(text)
        assert result == text


class TestRemoveInvisibleCharacters:
    def test_remove_null(self):
        assert remove_invisible_characters("a\x00b") == "ab"

    def test_remove_control_chars(self):
        text = "a\x01\x02b\x7f"
        assert remove_invisible_characters(text) == "ab"

    def test_preserve_newline(self):
        assert remove_invisible_characters("a\nb") == "a\nb"

    def test_preserve_tab(self):
        assert remove_invisible_characters("a\tb") == "a\tb"

    def test_preserve_carriage_return(self):
        # CR is preserved here but normalized later
        assert remove_invisible_characters("a\rb") == "a\rb"

    def test_remove_zero_width_space(self):
        assert remove_invisible_characters("a\u200bb") == "ab"

    def test_remove_bom(self):
        assert remove_invisible_characters("﻿a") == "a"

    def test_remove_soft_hyphen(self):
        assert remove_invisible_characters("a­b") == "ab"

    def test_remove_bidi_overrides(self):
        assert remove_invisible_characters("a\u202eb") == "ab"

    def test_empty_string(self):
        assert remove_invisible_characters("") == ""

    def test_remove_word_joiner(self):
        assert remove_invisible_characters("a⁠b") == "ab"

    def test_remove_arabic_letter_mark(self):
        assert remove_invisible_characters("a؜b") == "ab"


class TestNormalizeWhitespace:
    def test_crlf_to_lf(self):
        assert normalize_whitespace("a\r\nb") == "a\nb"

    def test_cr_to_lf(self):
        assert normalize_whitespace("a\rb") == "a\nb"

    def test_nbsp_to_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_thin_space_to_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_narrow_nbsp_to_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_ideographic_space_to_space(self):
        assert normalize_whitespace("a　b") == "a b"

    def test_en_quad_to_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_multiple_nonstandard_spaces(self):
        assert normalize_whitespace("   ") == "   "

    def test_preserve_multiple_spaces(self):
        assert normalize_whitespace("a  b") == "a  b"

    def test_preserve_trailing_spaces(self):
        assert normalize_whitespace("a  ") == "a  "

    def test_preserve_leading_spaces(self):
        assert normalize_whitespace("  a") == "  a"

    def test_mixed_line_endings(self):
        text = "a\r\nb\nc\rd"
        result = normalize_whitespace(text)
        assert result == "a\nb\nc\nd"

    def test_ogham_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_medium_mathematical_space(self):
        assert normalize_whitespace("a b") == "a b"

    def test_empty_string(self):
        assert normalize_whitespace("") == ""


class TestNormalizePipeline:
    def test_full_pipeline_basic(self):
        text = "RÓT NƯỚC\r\nVÀO"
        result = normalize(text)
        assert result == "RÓT NƯỚC\nVÀO"

    def test_full_pipeline_with_controls(self):
        text = "RÓT\x00NƯỚC\u200bVÀO"
        result = normalize(text)
        assert result == "RÓTNƯỚCVÀO"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_vietnamese_text_preserved(self):
        text = "LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ"
        result = normalize(text)
        assert result == text

    def test_mixed_with_ocr_noise(self):
        text = "SỐ MÙÔNG\x00(GẠT\u200bNGANG)\r\n"
        result = normalize(text)
        assert result == "SỐ MÙÔNG(GẠTNGANG)\n"

    def test_vietnamese_markdown_text(self):
        text = "- RÓT nước vào\n- PHA chế\n"
        result = normalize(text)
        assert result == text

    def test_tables_ish_text(self):
        text = "Sản phẩm | Số lượng\n--- | ---\nSữa | 2\n"
        result = normalize(text)
        assert result == text

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("", ""),
            ("\r\n", "\n"),
            ("\r", "\n"),
            (" ", " "),
            ("\u200b", ""),
            ("﻿", ""),
            ("hello\nworld", "hello\nworld"),
            ("\x00\x01\x02", ""),
        ],
    )
    def test_parametrized_edge_cases(self, input_text, expected):
        assert normalize(input_text) == expected

    def test_control_chars_outside_keep_range(self):
        # Preserve \n \r \t, remove everything else in C0 range except \r\n\t
        for cp in range(0x00, 0x09):  # 0x00-0x08
            assert normalize(chr(cp)) == "", f"U+{cp:04X} should be removed"
        assert normalize("\t") == "\t", "tab should be preserved"
        assert normalize("\n") == "\n", "LF should be preserved"
        assert normalize("\r") == "\n", "CR should become LF"

    def test_vietnamese_with_combining_marks(self):
        # NFD-style combining marks
        a_acute_nfd = "a" + "́"
        o_circ_nfd = "o" + "̂"
        u_horn_nfd = "u" + "̛"
        result = normalize(a_acute_nfd + o_circ_nfd + u_horn_nfd)
        assert unicodedata.is_normalized("NFC", result)

    def test_preserve_regular_punctuation(self):
        text = "Hello, world! How's it going? (yes)."
        assert normalize(text) == text
