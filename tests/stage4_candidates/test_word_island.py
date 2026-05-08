"""Tests for word-island extraction."""

from __future__ import annotations

from vn_corrector.common.enums import TokenType
from vn_corrector.common.spans import TextSpan, Token
from vn_corrector.stage4_candidates.word_island import (
    extract_word_islands,
    is_word_like_token,
    reconstruct_phrase_replacement,
)


def _make_token(
    text: str,
    token_type: TokenType = TokenType.VI_WORD,
    start: int = 0,
    end: int | None = None,
) -> Token:
    if end is None:
        end = start + len(text)
    return Token(text=text, token_type=token_type, span=TextSpan(start=start, end=end))


class TestIsWordLikeToken:
    def test_vi_word_is_word_like(self) -> None:
        t = _make_token("vay")
        assert is_word_like_token(t) is True

    def test_foreign_word_is_word_like(self) -> None:
        t = _make_token("iphone", token_type=TokenType.FOREIGN_WORD)
        assert is_word_like_token(t) is True

    def test_unknown_is_word_like(self) -> None:
        t = _make_token("xyz", token_type=TokenType.UNKNOWN)
        assert is_word_like_token(t) is True

    def test_space_not_word_like(self) -> None:
        t = _make_token(" ", token_type=TokenType.SPACE)
        assert is_word_like_token(t) is False

    def test_punctuation_not_word_like(self) -> None:
        t = _make_token("?", token_type=TokenType.PUNCT)
        assert is_word_like_token(t) is False

    def test_number_not_word_like(self) -> None:
        t = _make_token("15", token_type=TokenType.NUMBER)
        assert is_word_like_token(t) is False


class TestExtractWordIslands:
    def test_extracts_words_across_spaces(self) -> None:
        tokens = [
            _make_token("vay", start=0),
            _make_token(" ", token_type=TokenType.SPACE, start=3),
            _make_token("thi", start=4),
            _make_token(" ", token_type=TokenType.SPACE, start=7),
            _make_token("gio", start=8),
        ]
        islands = extract_word_islands(tokens)
        assert len(islands) == 1
        island = islands[0]
        assert island.raw_start == 0
        assert island.raw_end == 5
        assert tuple(t.text for t in island.word_tokens) == ("vay", "thi", "gio")
        assert island.raw_token_indexes == (0, 2, 4)

    def test_punctuation_breaks_island(self) -> None:
        tokens = [
            _make_token("vay", start=0),
            _make_token(" ", token_type=TokenType.SPACE, start=3),
            _make_token("thi", start=4),
            _make_token("???", token_type=TokenType.PUNCT, start=7),
            _make_token(" ", token_type=TokenType.SPACE, start=10),
            _make_token("gio", start=11),
        ]
        islands = extract_word_islands(tokens)
        assert len(islands) == 2
        assert tuple(t.text for t in islands[0].word_tokens) == ("vay", "thi")
        assert tuple(t.text for t in islands[1].word_tokens) == ("gio",)

    def test_preserves_raw_token_indexes(self) -> None:
        tokens = [
            _make_token("vay", start=0),
            _make_token(" ", token_type=TokenType.SPACE, start=3),
            _make_token("thi", start=4),
            _make_token("???", token_type=TokenType.PUNCT, start=7),
            _make_token("gio", start=10),
        ]
        islands = extract_word_islands(tokens)
        assert islands[0].raw_token_indexes == (0, 2)
        assert islands[1].raw_token_indexes == (4,)

    def test_empty_when_no_word_tokens(self) -> None:
        tokens = [
            _make_token(" ", token_type=TokenType.SPACE),
            _make_token("!", token_type=TokenType.PUNCT),
            _make_token(" ", token_type=TokenType.SPACE),
        ]
        islands = extract_word_islands(tokens)
        assert islands == []

    def test_protected_token_breaks_island(self) -> None:
        tokens = [
            _make_token("vay", start=0),
            _make_token(" ", token_type=TokenType.SPACE, start=3),
            _make_token("thi", start=4),
            _make_token("15", token_type=TokenType.NUMBER, start=7),
            _make_token(" ", token_type=TokenType.SPACE, start=9),
            _make_token("gio", start=10),
        ]
        islands = extract_word_islands(tokens)
        assert len(islands) == 2
        assert tuple(t.text for t in islands[0].word_tokens) == ("vay", "thi")
        assert tuple(t.text for t in islands[1].word_tokens) == ("gio",)

    def test_char_span_covers_island(self) -> None:
        tokens = [
            _make_token("vay", start=0, end=3),
            _make_token(" ", token_type=TokenType.SPACE, start=3, end=4),
            _make_token("thi", start=4, end=7),
        ]
        islands = extract_word_islands(tokens)
        assert len(islands) == 1
        assert islands[0].char_span.start == 0
        assert islands[0].char_span.end == 7


class TestReconstructPhraseReplacement:
    def test_reconstruct_preserves_spaces(self) -> None:
        tokens = [
            _make_token("vay", start=0, end=3),
            _make_token("   ", token_type=TokenType.SPACE, start=3, end=6),
            _make_token("thi", start=6, end=9),
        ]
        result = reconstruct_phrase_replacement(tokens, 0, 3, ("vậy", "thì"))
        assert result == "vậy   thì"

    def test_reconstruct_simple_space(self) -> None:
        tokens = [
            _make_token("vay", start=0, end=3),
            _make_token(" ", token_type=TokenType.SPACE, start=3, end=4),
            _make_token("thi", start=4, end=7),
        ]
        result = reconstruct_phrase_replacement(tokens, 0, 3, ("vậy", "thì"))
        assert result == "vậy thì"
