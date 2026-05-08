"""Word-island extraction — contiguous word-like correction islands.

Word islands group adjacent word-like tokens (``VI_WORD``, ``FOREIGN_WORD``,
``UNKNOWN``) that may span across ``SPACE`` tokens.  The lattice decoder
operates over these island positions, not raw tokenizer indexes.
"""

from __future__ import annotations

from dataclasses import dataclass

from vn_corrector.common.enums import TokenType
from vn_corrector.common.spans import TextSpan, Token

WORD_LIKE_TOKEN_TYPES: frozenset[TokenType] = frozenset(
    {
        TokenType.VI_WORD,
        TokenType.FOREIGN_WORD,
        TokenType.UNKNOWN,
    }
)


def is_word_like_token(token: Token) -> bool:
    """Return True if *token* is a word-like token (VI_WORD, FOREIGN_WORD, UNKNOWN)."""
    return token.token_type in WORD_LIKE_TOKEN_TYPES


@dataclass(frozen=True)
class WordIsland:
    """A contiguous correction island over word-like tokens.

    ``word_tokens`` are the word-like tokens only (no spaces/punctuation).
    ``raw_token_indexes`` maps each word token back to its position in the
    original token list.
    ``raw_start`` / ``raw_end`` are raw token positions in the original list
    (half-open range starting at raw_start inclusive).
    ``char_span`` is the full character span covering the island.
    """

    word_tokens: tuple[Token, ...]
    raw_token_indexes: tuple[int, ...]
    raw_start: int
    raw_end: int
    char_span: TextSpan


def extract_word_islands(tokens: list[Token]) -> list[WordIsland]:
    """Extract contiguous word-like correction islands from *tokens*.

    Spaces between word tokens do *not* break an island.  Punctuation,
    protected tokens, and non-word tokens do.
    """
    islands: list[WordIsland] = []
    current_word_tokens: list[Token] = []
    current_raw_indexes: list[int] = []

    def flush() -> None:
        if not current_word_tokens:
            return
        raw_start = current_raw_indexes[0]
        raw_end = current_raw_indexes[-1] + 1
        char_start = current_word_tokens[0].span.start
        char_end = current_word_tokens[-1].span.end
        islands.append(
            WordIsland(
                word_tokens=tuple(current_word_tokens),
                raw_token_indexes=tuple(current_raw_indexes),
                raw_start=raw_start,
                raw_end=raw_end,
                char_span=TextSpan(start=char_start, end=char_end),
            )
        )
        current_word_tokens.clear()
        current_raw_indexes.clear()

    for raw_idx, token in enumerate(tokens):
        if is_word_like_token(token):
            current_word_tokens.append(token)
            current_raw_indexes.append(raw_idx)
            continue

        if token.token_type == TokenType.SPACE:
            continue

        flush()

    flush()
    return islands


def reconstruct_phrase_replacement(
    raw_tokens: list[Token],
    raw_start: int,
    raw_end: int,
    output_tokens: tuple[str, ...],
) -> str:
    """Replace word tokens in *raw_tokens* with *output_tokens*, preserving separators.

    For each token in ``raw_tokens[raw_start:raw_end]``:
    - If it is a word-like token, replace with the next output token.
    - Otherwise (space, punctuation), preserve the original separator text.
    """
    output_iter = iter(output_tokens)
    pieces: list[str] = []
    for token in raw_tokens[raw_start:raw_end]:
        if is_word_like_token(token):
            pieces.append(next(output_iter))
        else:
            pieces.append(token.text)
    return "".join(pieces)
