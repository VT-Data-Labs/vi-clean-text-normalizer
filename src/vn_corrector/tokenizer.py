"""Tokenization with roundtrip guarantee: reconstruct(tokenize(text)) == text.

Splits text into fine-grained Token objects for downstream correction.
Whitespace, punctuation, and newlines are preserved verbatim so the
original text can always be reconstructed.
"""

from vn_corrector.common.enums import TokenType
from vn_corrector.common.spans import TextSpan, Token
from vn_corrector.utils.unicode import contains_vietnamese


def _char_class(ch: str) -> str:
    """Classify a single character into a token category."""
    if ch == "\n":
        return "NEWLINE"
    if ch.isdigit():
        return "NUMBER"
    if ch.isalpha():
        return "LETTER"
    if ch.isspace():
        return "SPACE"
    if ch.isprintable():
        return "PUNCT"
    return "UNKNOWN"


def tokenize(text: str) -> list[Token]:
    """Split *text* into a list of Token objects.

    Adjacent characters of the same class are grouped into one token.
    Letter groups are further classified as VI_WORD (if they contain any
    Vietnamese character) or FOREIGN_WORD (all non-Vietnamese letters).

    Guarantees: reconstruct(tokenize(text)) == text
    """
    if not text:
        return []

    tokens: list[Token] = []
    i = 0
    n = len(text)

    while i < n:
        cls = _char_class(text[i])
        start = i
        i += 1

        while i < n and _char_class(text[i]) == cls:
            i += 1

        token_text = text[start:i]
        span = TextSpan(start=start, end=i)

        if cls == "LETTER":
            tt = TokenType.VI_WORD if contains_vietnamese(token_text) else TokenType.FOREIGN_WORD
            tokens.append(Token(text=token_text, token_type=tt, span=span))
        elif cls == "NUMBER":
            tokens.append(Token(text=token_text, token_type=TokenType.NUMBER, span=span))
        elif cls == "NEWLINE":
            tokens.append(Token(text=token_text, token_type=TokenType.NEWLINE, span=span))
        elif cls == "SPACE":
            tokens.append(Token(text=token_text, token_type=TokenType.SPACE, span=span))
        elif cls == "PUNCT":
            tokens.append(Token(text=token_text, token_type=TokenType.PUNCT, span=span))
        else:
            tokens.append(Token(text=token_text, token_type=TokenType.UNKNOWN, span=span))

    return tokens


def reconstruct(tokens: list[Token]) -> str:
    """Reconstruct the original text from a list of Token objects."""
    return "".join(t.text for t in tokens)
