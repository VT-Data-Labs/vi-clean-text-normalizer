"""Tests for the Unicode normalizer (Stage 0 + Stage 1)."""

import unicodedata

import pytest

from vn_corrector.normalizer import (
    normalize,
    normalize_unicode,
    normalize_whitespace,
    remove_invisible_characters,
)
from vn_corrector.stage1_normalize.config import NormalizerConfig
from vn_corrector.stage1_normalize.engine import normalize as engine_normalize
from vn_corrector.stage1_normalize.steps.invisible import remove_invisible as step_remove_invisible
from vn_corrector.stage1_normalize.steps.unicode import normalize_unicode as step_normalize_unicode
from vn_corrector.stage1_normalize.steps.whitespace import (
    normalize_whitespace as step_normalize_whitespace,
)
from vn_corrector.stage1_normalize.types import NormalizedDocument

# ── Existing tests (backward compatibility) ──────────────────────────


class TestNormalizeUnicode:
    def test_nfc_preserves_already_normalized(self):
        text = "RÓT NƯỚC VÀO DỤNG CỤ"
        assert normalize_unicode(text) == text

    def test_nfd_to_nfc_conversion(self):
        r_acute_nfd = "R" + "́"  # R + combining acute
        o_circ_acute_nfd = "O" + "̂" + "́"  # O + circumflex + acute
        t = "T"
        nfd_text = r_acute_nfd + o_circ_acute_nfd + t
        result = normalize_unicode(nfd_text)
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
        assert remove_invisible_characters("a\rb") == "a\rb"

    def test_remove_zero_width_space(self):
        assert remove_invisible_characters("a​b") == "ab"

    def test_remove_bom(self):
        assert remove_invisible_characters("﻿a") == "a"

    def test_remove_soft_hyphen(self):
        assert remove_invisible_characters("a­b") == "ab"

    def test_remove_bidi_overrides(self):
        assert remove_invisible_characters("a‮b") == "ab"

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
        text = "RÓT\x00NƯỚC​VÀO"
        result = normalize(text)
        assert result == "RÓTNƯỚCVÀO"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_vietnamese_text_preserved(self):
        text = "LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ"
        result = normalize(text)
        assert result == text

    def test_mixed_with_ocr_noise(self):
        text = "SỐ MÙÔNG\x00(GẠT​NGANG)\r\n"
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
            ("​", ""),
            ("﻿", ""),
            ("hello\nworld", "hello\nworld"),
            ("\x00\x01\x02", ""),
        ],
    )
    def test_parametrized_edge_cases(self, input_text, expected):
        assert normalize(input_text) == expected

    def test_control_chars_outside_keep_range(self):
        for cp in range(0x00, 0x09):
            assert normalize(chr(cp)) == "", f"U+{cp:04X} should be removed"
        assert normalize("\t") == "\t", "tab should be preserved"
        assert normalize("\n") == "\n", "LF should be preserved"
        assert normalize("\r") == "\n", "CR should become LF"

    def test_vietnamese_with_combining_marks(self):
        a_acute_nfd = "a" + "́"
        o_circ_nfd = "o" + "̂"
        u_horn_nfd = "u" + "̛"
        result = normalize(a_acute_nfd + o_circ_nfd + u_horn_nfd)
        assert unicodedata.is_normalized("NFC", result)

    def test_preserve_regular_punctuation(self):
        text = "Hello, world! How's it going? (yes)."
        assert normalize(text) == text


# ── New tests for the refactored module ──────────────────────────────


class TestNormalizedDocumentType:
    """Verify :class:`NormalizedDocument` dataclass."""

    def test_fields(self):
        doc = NormalizedDocument(
            original_text="hello​ world\r\n",
            normalized_text="hello world\n",
            steps_applied=["normalize_unicode", "remove_invisible", "normalize_whitespace"],
            stats={"removed_zero_width": 1, "normalized_linebreaks": 1},
        )
        assert doc.original_text == "hello​ world\r\n"
        assert doc.normalized_text == "hello world\n"
        assert len(doc.steps_applied) == 3
        assert doc.stats["removed_zero_width"] == 1

    def test_defaults(self):
        doc = NormalizedDocument(original_text="", normalized_text="")
        assert doc.steps_applied == []
        assert doc.stats == {}

    def test_repr(self):
        doc = NormalizedDocument(original_text="a", normalized_text="b")
        r = repr(doc)
        assert "original_text='a'" in r
        assert "normalized_text='b'" in r


class TestNormalizerConfig:
    """Verify configuration dataclass."""

    def test_defaults_enabled(self):
        cfg = NormalizerConfig()
        assert cfg.normalize_unicode is True
        assert cfg.remove_invisible is True
        assert cfg.normalize_whitespace is True

    def test_disable_unicode(self):
        cfg = NormalizerConfig(normalize_unicode=False)
        result = engine_normalize("á", config=cfg)
        # Without unicode step, combining mark stays
        assert "́" in result.normalized_text
        assert "normalize_unicode" not in result.steps_applied

    def test_disable_invisible(self):
        cfg = NormalizerConfig(remove_invisible=False)
        result = engine_normalize("a​b", config=cfg)
        assert "​" in result.normalized_text
        assert "remove_invisible" not in result.steps_applied

    def test_disable_whitespace(self):
        cfg = NormalizerConfig(normalize_whitespace=False)
        result = engine_normalize("a\r\nb", config=cfg)
        assert "\r\n" in result.normalized_text
        assert "normalize_whitespace" not in result.steps_applied

    def test_future_proofing_fields(self):
        cfg = NormalizerConfig(
            detect_language=True,
            ocr_confidence_aware=True,
            markdown_aware=True,
            extra_steps=["custom_step"],
        )
        assert cfg.detect_language is True
        assert cfg.extra_steps == ["custom_step"]


class TestEngineStats:
    """Verify stats tracking in the pipeline."""

    def test_clean_text_no_changes(self):
        doc = engine_normalize("Hello world\n")
        assert doc.stats.get("unicode_changes", 0) == 0
        assert doc.stats.get("removed_control", 0) == 0
        assert doc.stats.get("converted_spaces", 0) == 0
        assert doc.stats.get("normalized_linebreaks", 0) == 0

    def test_unicode_changes_counted(self):
        a_acute_nfd = "a" + "́"
        doc = engine_normalize(a_acute_nfd)
        assert doc.stats.get("unicode_changes", 0) > 0

    def test_invisible_removal_categorized(self):
        text = (
            "a\x00b"  # control
            "​c"  # zero-width
            "‮d"  # bidi
            "﻿e"  # BOM
        )
        doc = engine_normalize(text)
        assert doc.stats.get("removed_control", 0) >= 1
        assert doc.stats.get("removed_zero_width", 0) >= 1
        assert doc.stats.get("removed_bidi", 0) >= 1
        assert doc.stats.get("removed_bom", 0) >= 1
        assert doc.normalized_text == "abcde"

    def test_whitespace_stats(self):
        doc = engine_normalize("a\r\nb c")
        assert doc.stats.get("converted_spaces", 0) >= 1
        assert doc.stats.get("normalized_linebreaks", 0) >= 1

    def test_acceptance_criteria(self):
        doc = engine_normalize("hello​ world\r\n")
        assert doc.normalized_text == "hello world\n"
        assert doc.stats.get("removed_zero_width", 0) == 1
        assert doc.stats.get("normalized_linebreaks", 0) == 1

    def test_steps_applied_order(self):
        doc = engine_normalize("hello")
        assert doc.steps_applied == [
            "normalize_unicode",
            "remove_invisible",
            "normalize_whitespace",
        ]


class TestStepFunctions:
    """Verify new step functions produce correct tuples."""

    def test_unicode_step_returns_tuple(self):
        result = step_normalize_unicode("abc")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_invisible_step_returns_tuple(self):
        result = step_remove_invisible("abc")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert "removed_control" in result[1]

    def test_whitespace_step_returns_tuple(self):
        result = step_normalize_whitespace("abc")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert "converted_spaces" in result[1]
        assert "normalized_linebreaks" in result[1]

    def test_unicode_step_zero_changes(self):
        text, stats = step_normalize_unicode("NFC OK")
        assert stats["unicode_changes"] == 0
        assert text == "NFC OK"

    def test_invisible_step_empty_string(self):
        text, stats = step_remove_invisible("")
        assert text == ""
        assert sum(stats.values()) == 0

    def test_whitespace_step_empty_string(self):
        text, stats = step_normalize_whitespace("")
        assert text == ""
        assert sum(stats.values()) == 0


class TestIdempotency:
    """Invariant: normalize(normalize(text)) == normalize(text)."""

    def test_plain_text(self):
        t1 = engine_normalize("Hello world")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_vietnamese_upper(self):
        t1 = engine_normalize("RÓT NƯỚC VÀO DỤNG CỤ")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_with_invisible(self):
        t1 = engine_normalize("a\x00b​c")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_with_whitespace(self):
        t1 = engine_normalize("a  \r\nb c")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_mixed_ocr_noise(self):
        t1 = engine_normalize("SỐ MÙÔNG\x00(GẠT​NGANG)\r\n")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_nfd_then_normalize(self):
        a_acute_nfd = "a" + "́"
        t1 = engine_normalize(a_acute_nfd)
        t2 = engine_normalize(t1.normalized_text)
        assert t2.normalized_text == t1.normalized_text

    def test_second_pass_stats_are_zero(self):
        """After idempotent normalization, second pass should change nothing."""
        t1 = engine_normalize("hello​ world\r\n")
        t2 = engine_normalize(t1.normalized_text)
        assert t2.stats.get("unicode_changes", 0) == 0
        assert t2.stats.get("removed_control", 0) == 0
        assert t2.stats.get("removed_zero_width", 0) == 0
        assert t2.stats.get("removed_bidi", 0) == 0
        assert t2.stats.get("removed_bom", 0) == 0
        assert t2.stats.get("converted_spaces", 0) == 0
        assert t2.stats.get("normalized_linebreaks", 0) == 0


class TestInvariants:
    """Character preservation and length sanity."""

    def test_visible_chars_preserved(self):
        text = "RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ"
        doc = engine_normalize(text)
        # All visible characters should still be present
        for ch in text:
            if ch.isprintable() and not ch.isspace():
                assert ch in doc.normalized_text, f"'{ch}' U+{ord(ch):04X} missing"

    def test_length_not_drastically_reduced(self):
        text = "Hello, this is a normal sentence with some content."
        doc = engine_normalize(text)
        # Length should be similar (smaller only if invisible chars removed)
        assert len(doc.normalized_text) >= len(text) - 5

    def test_empty_string(self):
        doc = engine_normalize("")
        assert doc.normalized_text == ""
        assert doc.original_text == ""
