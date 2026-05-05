"""Unicode normalization step — NFC canonical composition."""

import itertools
import unicodedata


def normalize_unicode(text: str) -> tuple[str, dict[str, int]]:
    """Normalize Unicode to NFC (Canonical Composition).

    NFC composes decomposed characters (NFD/NFKD) into their canonical
    precomposed forms, which is the standard for Vietnamese text.

    Returns:
        Tuple of (normalized_text, stats) where stats contains
        ``unicode_changes`` — the number of codepoint positions that
        changed during normalization.

    """
    if unicodedata.is_normalized("NFC", text):
        return text, {"unicode_changes": 0}

    normalized = unicodedata.normalize("NFC", text)

    # Count how many codepoint positions changed.  Use zip_longest
    # because normalization can change string length (NFD→NFC shortens).
    changes = sum(1 for a, b in itertools.zip_longest(text, normalized) if a != b)
    return normalized, {"unicode_changes": changes}
