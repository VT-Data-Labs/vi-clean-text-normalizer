"""Tests for the tokenizer — roundtrip guarantee and token type classification."""

import pytest

from vn_corrector.tokenizer import reconstruct, tokenize

# ---------------------------------------------------------------------------
# Roundtrip guarantee
# ---------------------------------------------------------------------------


class TestRoundtrip:
    """reconstruct(tokenize(text)) must always equal the original text."""

    def test_empty_string(self):
        assert not tokenize("")
        assert reconstruct([]) == ""

    def test_basic_text(self):
        text = "RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ"
        assert reconstruct(tokenize(text)) == text

    def test_vietnamese_with_punctuation(self):
        text = "SỐ MÙÔNG (GẠT NGANG)"
        assert reconstruct(tokenize(text)) == text

    def test_markdown_bullets(self):
        text = "- RÓT nước vào\n- PHA chế\n"
        assert reconstruct(tokenize(text)) == text

    def test_tables_ish(self):
        text = "Sản phẩm | Số lượng\n--- | ---\nSữa | 2\n"
        assert reconstruct(tokenize(text)) == text

    def test_multiple_spaces(self):
        text = "hello   world"
        assert reconstruct(tokenize(text)) == text

    def test_leading_trailing_spaces(self):
        text = "  hello world  "
        assert reconstruct(tokenize(text)) == text

    def test_multiple_newlines(self):
        text = "hello\n\n\nworld"
        assert reconstruct(tokenize(text)) == text

    def test_mixed_newline_and_spaces(self):
        text = "hello\n  world\n  foo"
        assert reconstruct(tokenize(text)) == text

    def test_only_spaces(self):
        text = "     "
        assert reconstruct(tokenize(text)) == text

    def test_only_newlines(self):
        text = "\n\n\n"
        assert reconstruct(tokenize(text)) == text

    def test_special_punctuation(self):
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        assert reconstruct(tokenize(text)) == text

    def test_numbers_and_units(self):
        text = "Nhiệt độ 40°C - 120ml nước"
        assert reconstruct(tokenize(text)) == text

    def test_vietnamese_with_tabs(self):
        text = "SỐ\tMÙÔNG\t(GẠT NGANG)"
        assert reconstruct(tokenize(text)) == text

    def test_ocr_messy_text(self):
        text = "SỐ MÙÔNG (GẠT NGANG) - 120ml\nRỐT NƯỚC VÀO"
        assert reconstruct(tokenize(text)) == text

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "a",
            " ",
            "\n",
            "hello world",
            "  hello  world  ",
            "a\nb\nc",
            "\n\n\na\n\n\n",
            "!@# $%^ &*()",
            "123 456 789",
            "Đường Lê Lợi",
            "RỐT NƯỚC VÀO DỤNG CỤ",
        ],
    )
    def test_parametrized_roundtrip(self, text):
        assert reconstruct(tokenize(text)) == text


# ---------------------------------------------------------------------------
# Token type classification
# ---------------------------------------------------------------------------


class TestTokenTypes:
    def test_vi_word(self):
        tokens = tokenize("nước")
        assert len(tokens) == 1
        assert tokens[0].token_type == "VI_WORD"
        assert tokens[0].text == "nước"

    def test_vi_word_upper(self):
        tokens = tokenize("NƯỚC")
        assert len(tokens) == 1
        assert tokens[0].token_type == "VI_WORD"

    def test_foreign_word(self):
        tokens = tokenize("hello")
        assert len(tokens) == 1
        assert tokens[0].token_type == "FOREIGN_WORD"

    def test_number(self):
        tokens = tokenize("123")
        assert len(tokens) == 1
        assert tokens[0].token_type == "NUMBER"

    def test_space(self):
        tokens = tokenize("   ")
        assert len(tokens) == 1
        assert tokens[0].token_type == "SPACE"
        assert tokens[0].text == "   "

    def test_newline(self):
        tokens = tokenize("\n")
        assert len(tokens) == 1
        assert tokens[0].token_type == "NEWLINE"

    def test_punctuation(self):
        tokens = tokenize("(")
        assert len(tokens) == 1
        assert tokens[0].token_type == "PUNCT"

    def test_punctuation_grouped(self):
        tokens = tokenize("...")
        assert len(tokens) == 1
        assert tokens[0].token_type == "PUNCT"
        assert tokens[0].text == "..."

    def test_mixed_sentence(self):
        tokens = tokenize("SỐ MÙÔNG (GẠT NGANG)")
        types = [t.token_type for t in tokens]
        # "NGANG" has no Vietnamese diacritics → FOREIGN_WORD
        assert types == [
            "VI_WORD",
            "SPACE",
            "VI_WORD",
            "SPACE",
            "PUNCT",
            "VI_WORD",
            "SPACE",
            "FOREIGN_WORD",
            "PUNCT",
        ]

    def test_mixed_vi_and_foreign(self):
        tokens = tokenize("DHA và ARA")
        types = [t.token_type for t in tokens]
        assert types == ["FOREIGN_WORD", "SPACE", "VI_WORD", "SPACE", "FOREIGN_WORD"]

    def test_markdown_bullet(self):
        tokens = tokenize("- RÓT nước vào\n- PHA chế\n")
        types = [t.token_type for t in tokens]
        # "PHA" has no Vietnamese diacritics → FOREIGN_WORD
        assert types == [
            "PUNCT",
            "SPACE",
            "VI_WORD",
            "SPACE",
            "VI_WORD",
            "SPACE",
            "VI_WORD",
            "NEWLINE",
            "PUNCT",
            "SPACE",
            "FOREIGN_WORD",
            "SPACE",
            "VI_WORD",
            "NEWLINE",
        ]

    def test_table_row(self):
        tokens = tokenize("Sản phẩm | Số lượng\n--- | ---\n")
        types = [t.token_type for t in tokens]
        assert types == [
            "VI_WORD",
            "SPACE",
            "VI_WORD",
            "SPACE",
            "PUNCT",
            "SPACE",
            "VI_WORD",
            "SPACE",
            "VI_WORD",
            "NEWLINE",
            "PUNCT",
            "SPACE",
            "PUNCT",
            "SPACE",
            "PUNCT",
            "NEWLINE",
        ]


# ---------------------------------------------------------------------------
# OCR edge cases
# ---------------------------------------------------------------------------


class TestOcrEdgeCases:
    def test_number_letter_mixed(self):
        tokens = tokenize("120m2")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "FOREIGN_WORD", "NUMBER"]
        texts = [t.text for t in tokens]
        assert texts == ["120", "m", "2"]

    def test_three_ty_seventy_five(self):
        tokens = tokenize("3ty75")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "FOREIGN_WORD", "NUMBER"]
        texts = [t.text for t in tokens]
        assert texts == ["3", "ty", "75"]

    def test_two_pn(self):
        tokens = tokenize("2PN")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "FOREIGN_WORD"]
        texts = [t.text for t in tokens]
        assert texts == ["2", "PN"]

    def test_dash_separated_digits(self):
        tokens = tokenize("5-10 phút")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "PUNCT", "NUMBER", "SPACE", "VI_WORD"]
        texts = [t.text for t in tokens]
        assert texts == ["5", "-", "10", " ", "phút"]

    def test_number_at_end(self):
        tokens = tokenize("phút 10")
        types = [t.token_type for t in tokens]
        assert types == ["VI_WORD", "SPACE", "NUMBER"]

    def test_number_with_vietnamese_letter(self):
        tokens = tokenize("120ml")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "FOREIGN_WORD"]
        texts = [t.text for t in tokens]
        assert texts == ["120", "ml"]

    def test_temperature(self):
        tokens = tokenize("40°C")
        types = [t.token_type for t in tokens]
        assert types == ["NUMBER", "PUNCT", "FOREIGN_WORD"]
        texts = [t.text for t in tokens]
        assert texts == ["40", "°", "C"]

    def test_compound_number_units(self):
        tokens = tokenize("3ty75 120m2 2PN")
        types = [t.token_type for t in tokens]
        assert types == [
            "NUMBER",
            "FOREIGN_WORD",
            "NUMBER",
            "SPACE",
            "NUMBER",
            "FOREIGN_WORD",
            "NUMBER",
            "SPACE",
            "NUMBER",
            "FOREIGN_WORD",
        ]


# ---------------------------------------------------------------------------
# Protected field (tokenizer does not set it)
# ---------------------------------------------------------------------------


class TestProtectedField:
    def test_protected_defaults_false(self):
        tokens = tokenize("hello")
        assert all(not t.protected for t in tokens)

    def test_mixed_tokens_not_protected(self):
        tokens = tokenize("SỐ MÙÔNG (GẠT NGANG)")
        assert all(not t.protected for t in tokens)

    def test_numbers_not_protected(self):
        tokens = tokenize("120 30 5")
        assert all(not t.protected for t in tokens)

    def test_newlines_not_protected(self):
        tokens = tokenize("\n\n")
        assert all(not t.protected for t in tokens)
