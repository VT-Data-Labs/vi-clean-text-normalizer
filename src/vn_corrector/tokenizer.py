"""Tokenization with roundtrip guarantee: reconstruct(tokenize(text)) == text.

Splits text into fine-grained Token objects for downstream correction.
Whitespace, punctuation, and newlines are preserved verbatim so the
original text can always be reconstructed.
"""

from vn_corrector.common.types import Token
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

        if cls == "LETTER":
            token_type = "VI_WORD" if contains_vietnamese(token_text) else "FOREIGN_WORD"
            tokens.append(Token(token_text, token_type))
        elif cls == "NUMBER":
            tokens.append(Token(token_text, "NUMBER"))
        elif cls == "NEWLINE":
            tokens.append(Token(token_text, "NEWLINE"))
        elif cls == "SPACE":
            tokens.append(Token(token_text, "SPACE"))
        elif cls == "PUNCT":
            tokens.append(Token(token_text, "PUNCT"))
        else:
            tokens.append(Token(token_text, "UNKNOWN"))

    return tokens


def reconstruct(tokens: list[Token]) -> str:
    """Reconstruct the original text from a list of Token objects."""
    return "".join(t.text for t in tokens)
