"""Stage 0 + Stage 1: Input Normalization and Unicode Normalization.

Responsibilities:
- Normalize Unicode to NFC.
- Remove/replace invisible and control characters.
- Normalize whitespace without destroying intentional newlines.
- Preserve Vietnamese characters and markdown-like text.

This module does NOT:
- Restore Vietnamese diacritics.
- Perform dictionary correction.
- Use LLMs or external models.
"""

import re
import unicodedata

# Invisible/control characters to remove entirely.
# Preserves: \n (LF), \r (CR - normalized later), \t (tab - kept as token whitespace).
_INVISIBLE_RE = re.compile(
    r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f"  # C0 controls (keep \n\r\t)
    r"\u00ad"  # soft hyphen
    r"\u061c"  # arabic letter mark
    r"\u200b-\u200f"  # zero-width space, ZWNJ, ZWJ, LRM, RLM
    r"\u2028\u2029"  # line/paragraph separator (redundant with \n)
    r"\u202a-\u202e"  # bidi overrides
    r"\u2060-\u2064"  # word joiner, invisible operators
    r"\ufeff"  # BOM / zero-width no-break space
    r"]"
)

# Non-standard space characters → convert to regular space.
_NONSTANDARD_SPACE_RE = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")


def normalize(text: str) -> str:
    """Apply the full normalization pipeline.

    Steps:
    1. Unicode NFC normalization.
    2. Remove invisible/control characters.
    3. Normalize whitespace (line endings, non-standard spaces).
    """
    text = normalize_unicode(text)
    text = remove_invisible_characters(text)
    text = normalize_whitespace(text)
    return text


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC (Canonical Composition).

    NFC composes decomposed characters (NFD/NFKD) into their canonical
    precomposed forms, which is the standard for Vietnamese text.

    Examples:
        'n̂' (n + combining circumflex) → 'n'  (not canonical)
        Actually NFC ensures canonical compositions are used.

    """
    return unicodedata.normalize("NFC", text)


def remove_invisible_characters(text: str) -> str:
    r"""Remove invisible and non-printing control characters.

    Preserves:
    - \n (newline), \r (carriage return), \t (tab)
    - Printable characters including Vietnamese letters
    - Normal punctuation and symbols
    """
    return _INVISIBLE_RE.sub("", text)


def normalize_whitespace(text: str) -> str:
    r"""Normalize whitespace while preserving intentional newlines.

    - Converts non-standard spaces (NBSP, thin space, etc.) to regular space.
    - Normalizes line endings: \r\n → \n, standalone \r → \n.
    - Does NOT collapse multiple spaces (preserves formatting).
    - Does NOT trim leading/trailing whitespace.

    Returns:
        Text with normalized line endings and standard spaces.

    """
    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    # Convert non-standard spaces to regular space
    text = _NONSTANDARD_SPACE_RE.sub(" ", text)
    return text
