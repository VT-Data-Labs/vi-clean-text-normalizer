"""Canonical Vietnamese character normalisation.

This is the **single source of truth** for all Vietnamese accent stripping,
lookalike character fixing, and text normalisation in the system.

All downstream modules (Stage-2 lexicon, build scripts, validators) **must**
import from here — never duplicate these functions elsewhere.

Exports
-------
- ``VIETNAMESE_ACCENT_MAP`` — codepoint → base letter
- ``fix_lookalikes()`` — replace common Unicode lookalike errors
- ``strip_accents()`` — lower-case + remove all Vietnamese tone marks
- ``strip_accents_preserve_case()`` — remove tone marks, keep casing
- ``strip_vietnamese_accents()`` — alias for *strip_accents*
- ``to_no_tone_key()`` — stable no-tone lookup key
- ``normalize_text()`` — NFC + fix_lookalikes + lowercase (+ collapse whitespace)
- ``normalize_key()`` — canonical lexicon key (accentless + whitespace-collapsed)
"""

from __future__ import annotations

import re as _re
import unicodedata as _unicodedata

# ---------------------------------------------------------------------------
# Vietnamese accent map — vietnamese-alphabet-only
# ---------------------------------------------------------------------------

VIETNAMESE_ACCENT_MAP: dict[str, str] = {
    # a with tones
    "à": "a",
    "á": "a",
    "ả": "a",
    "ã": "a",
    "ạ": "a",
    # ă (a-breve) and its tones
    "ă": "a",
    "ằ": "a",
    "ắ": "a",
    "ẳ": "a",
    "ẵ": "a",
    "ặ": "a",
    # â (a-circumflex) and its tones
    "â": "a",
    "ầ": "a",
    "ấ": "a",
    "ẩ": "a",
    "ẫ": "a",
    "ậ": "a",
    # e with tones
    "è": "e",
    "é": "e",
    "ẻ": "e",
    "ẽ": "e",
    "ẹ": "e",
    # ê (e-circumflex) and its tones
    "ê": "e",
    "ề": "e",
    "ế": "e",
    "ể": "e",
    "ễ": "e",
    "ệ": "e",
    # i with tones
    "ì": "i",
    "í": "i",
    "ỉ": "i",
    "ĩ": "i",
    "ị": "i",
    # o with tones
    "ò": "o",
    "ó": "o",
    "ỏ": "o",
    "õ": "o",
    "ọ": "o",
    # ô (o-circumflex) and its tones
    "ô": "o",
    "ồ": "o",
    "ố": "o",
    "ổ": "o",
    "ỗ": "o",
    "ộ": "o",
    # ơ (o-horn) and its tones
    "ơ": "o",
    "ờ": "o",
    "ớ": "o",
    "ở": "o",
    "ỡ": "o",
    "ợ": "o",
    # u with tones
    "ù": "u",
    "ú": "u",
    "ủ": "u",
    "ũ": "u",
    "ụ": "u",
    # ư (u-horn) and its tones
    "ư": "u",
    "ừ": "u",
    "ứ": "u",
    "ử": "u",
    "ữ": "u",
    "ự": "u",
    # y with tones
    "ỳ": "y",
    "ý": "y",
    "ỷ": "y",
    "ỹ": "y",
    "ỵ": "y",
    # đ (d with stroke)
    "đ": "d",
    # --- UPPERCASE ---
    "À": "A",
    "Á": "A",
    "Ả": "A",
    "Ã": "A",
    "Ạ": "A",
    "Ă": "A",
    "Ằ": "A",
    "Ắ": "A",
    "Ẳ": "A",
    "Ẵ": "A",
    "Ặ": "A",
    "Â": "A",
    "Ầ": "A",
    "Ấ": "A",
    "Ẩ": "A",
    "Ẫ": "A",
    "Ậ": "A",
    "È": "E",
    "É": "E",
    "Ẻ": "E",
    "Ẽ": "E",
    "Ẹ": "E",
    "Ê": "E",
    "Ề": "E",
    "Ế": "E",
    "Ể": "E",
    "Ễ": "E",
    "Ệ": "E",
    "Ì": "I",
    "Í": "I",
    "Ỉ": "I",
    "Ĩ": "I",
    "Ị": "I",
    "Ò": "O",
    "Ó": "O",
    "Ỏ": "O",
    "Õ": "O",
    "Ọ": "O",
    "Ô": "O",
    "Ồ": "O",
    "Ố": "O",
    "Ổ": "O",
    "Ỗ": "O",
    "Ộ": "O",
    "Ơ": "O",
    "Ờ": "O",
    "Ớ": "O",
    "Ở": "O",
    "Ỡ": "O",
    "Ợ": "O",
    "Ù": "U",
    "Ú": "U",
    "Ủ": "U",
    "Ũ": "U",
    "Ụ": "U",
    "Ư": "U",
    "Ừ": "U",
    "Ứ": "U",
    "Ử": "U",
    "Ữ": "U",
    "Ự": "U",
    "Ỳ": "Y",
    "Ý": "Y",
    "Ỷ": "Y",
    "Ỹ": "Y",
    "Ỵ": "Y",
    "Đ": "D",
}

# Lower-cased version of the map — all values are lowercase base letters
_MAP_LOWER: dict[str, str] = {k: v.lower() for k, v in VIETNAMESE_ACCENT_MAP.items()}

# ---------------------------------------------------------------------------
# Lookalike fix — common Unicode substitution errors
# ---------------------------------------------------------------------------

_LOOKALIKE_FIX: dict[str, str] = {
    "\u00f0": "đ",  # LATIN SMALL LETTER ETH (Icelandic) → Vietnamese đ
    "\u00d0": "Đ",  # LATIN CAPITAL LETTER ETH (Icelandic) → Vietnamese Đ
    "\u0257": "đ",  # LATIN SMALL LETTER D WITH HOOK → Vietnamese đ
    "\u014f": "ơ",  # LATIN SMALL LETTER O WITH BREVE → o with horn (ơ)
    "\u2013": "-",  # EN DASH → hyphen
    "\u2014": "-",  # EM DASH → hyphen
    "\u2018": "'",  # LEFT SINGLE QUOTATION MARK → apostrophe
    "\u2019": "'",  # RIGHT SINGLE QUOTATION MARK → apostrophe
    "\u201c": '"',  # LEFT DOUBLE QUOTATION MARK → quote
    "\u201d": '"',  # RIGHT DOUBLE QUOTATION MARK → quote
}

_WHITESPACE_RE = _re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fix_lookalikes(text: str) -> str:
    """Replace common Vietnamese lookalike Unicode errors with correct codepoints.

    Examples
    --------
    >>> fix_lookalikes("anh ðào")  # U+00F0 (Icelandic eth) → đ
    "anh đào"
    >>> fix_lookalikes("sŏ")  # U+014F (o with breve) → ơ
    "sơ"
    """
    return "".join(_LOOKALIKE_FIX.get(ch, ch) for ch in text)


def strip_accents(text: str) -> str:
    """Strip Vietnamese accents and return lowercase ASCII.

    The result is always lowercased.

    Parameters
    ----------
    text:
        Input text possibly containing Vietnamese accented characters.

    Returns
    -------
    str
        Lowercase string with all accents stripped to base ASCII letters.

    Examples
    --------
    >>> strip_accents("SỐ MUỖNG")
    "so muong"
    >>> strip_accents("đường")
    "duong"
    """
    return "".join(_MAP_LOWER.get(ch, ch.lower()) for ch in text)


def strip_accents_preserve_case(text: str) -> str:
    """Strip Vietnamese accents while preserving original case.

    Parameters
    ----------
    text:
        Input text possibly containing Vietnamese accented characters.

    Returns
    -------
    str
        String with all accents stripped, keeping original casing.

    Examples
    --------
    >>> strip_accents_preserve_case("Đường")
    "Duong"
    """
    return "".join(VIETNAMESE_ACCENT_MAP.get(ch, ch) for ch in text)


def strip_vietnamese_accents(text: str) -> str:
    """Alias for :func:`strip_accents`."""
    return strip_accents(text)


def to_no_tone_key(text: str) -> str:
    """Convert Vietnamese text to a stable lowercase no-tone lookup key.

    Strips all Vietnamese diacritics and tone marks, converts Đ/đ to d,
    and lowercases the result. This produces a repeatable key for
    accent-insensitive lexicon lookups.

    Examples
    --------
    >>> to_no_tone_key("đường")
    "duong"
    >>> to_no_tone_key("Sổ hồng")
    "so hong"
    """
    return strip_accents(text)


def normalize_text(text: str) -> str:
    """NFC-normalize, fix lookalike chars, lowercase, collapse whitespace.

    This is the **canonical text normalisation** used when ingesting
    external dictionary data.  It ensures that visually identical but
    Unicode-distinct characters are mapped to the same canonical form.

    Parameters
    ----------
    text:
        Raw input text.

    Returns
    -------
    str
        NFC-normalised, lookalike-fixed, lowercased, whitespace-collapsed text.

    Examples
    --------
    >>> normalize_text("MuỖNG")
    "muỗng"
    >>> normalize_text("anh ðào")
    "anh đào"
    """
    if not text or not text.strip():
        return ""
    nfc = _unicodedata.normalize("NFC", text)
    fixed = fix_lookalikes(nfc)
    lowered = fixed.strip().lower()
    return _WHITESPACE_RE.sub(" ", lowered)


def normalize_key(text: str) -> str:
    """Canonical lexicon key — accentless + whitespace-collapsed.

    **Invariant**::

        normalize_key("Muỗng") == normalize_key("muong")  # → "muong"

    Steps
    -----
    1. Lowercase all characters and strip Vietnamese tone marks.
    2. Collapse runs of whitespace to a single space.
    3. Strip leading/trailing whitespace.

    Parameters
    ----------
    text:
        Input text, possibly containing Vietnamese accented characters.

    Returns
    -------
    str
        A lower-case, accentless, whitespace-normalised string suitable
        for use as a dictionary key.
    """
    if not text or not text.strip():
        return ""
    no_accents = strip_accents(text)
    return _WHITESPACE_RE.sub(" ", no_accents).strip()
