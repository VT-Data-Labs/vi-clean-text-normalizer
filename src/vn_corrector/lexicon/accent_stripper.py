"""Vietnamese accent stripping utilities."""

from __future__ import annotations

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
    # A with tones
    "À": "A",
    "Á": "A",
    "Ả": "A",
    "Ã": "A",
    "Ạ": "A",
    # Ă (A-breve) and its tones
    "Ă": "A",
    "Ằ": "A",
    "Ắ": "A",
    "Ẳ": "A",
    "Ẵ": "A",
    "Ặ": "A",
    # Â (A-circumflex) and its tones
    "Â": "A",
    "Ầ": "A",
    "Ấ": "A",
    "Ẩ": "A",
    "Ẫ": "A",
    "Ậ": "A",
    # E with tones
    "È": "E",
    "É": "E",
    "Ẻ": "E",
    "Ẽ": "E",
    "Ẹ": "E",
    # Ê (E-circumflex) and its tones
    "Ê": "E",
    "Ề": "E",
    "Ế": "E",
    "Ể": "E",
    "Ễ": "E",
    "Ệ": "E",
    # I with tones
    "Ì": "I",
    "Í": "I",
    "Ỉ": "I",
    "Ĩ": "I",
    "Ị": "I",
    # O with tones
    "Ò": "O",
    "Ó": "O",
    "Ỏ": "O",
    "Õ": "O",
    "Ọ": "O",
    # Ô (O-circumflex) and its tones
    "Ô": "O",
    "Ồ": "O",
    "Ố": "O",
    "Ổ": "O",
    "Ỗ": "O",
    "Ộ": "O",
    # Ơ (O-horn) and its tones
    "Ơ": "O",
    "Ờ": "O",
    "Ớ": "O",
    "Ở": "O",
    "Ỡ": "O",
    "Ợ": "O",
    # U with tones
    "Ù": "U",
    "Ú": "U",
    "Ủ": "U",
    "Ũ": "U",
    "Ụ": "U",
    # Ư (U-horn) and its tones
    "Ư": "U",
    "Ừ": "U",
    "Ứ": "U",
    "Ử": "U",
    "Ữ": "U",
    "Ự": "U",
    # Y with tones
    "Ỳ": "Y",
    "Ý": "Y",
    "Ỷ": "Y",
    "Ỹ": "Y",
    "Ỵ": "Y",
    # Đ (D with stroke)
    "Đ": "D",
}

_MAP_LOWER: dict[str, str] = {k: v.lower() for k, v in VIETNAMESE_ACCENT_MAP.items()}


def strip_accents(text: str) -> str:
    """Strip Vietnamese accents and return lowercase ASCII.

    Args:
        text: Input text possibly containing Vietnamese accented characters.

    Returns:
        Lowercase string with all accents stripped to base ASCII letters.

    """
    return "".join(_MAP_LOWER.get(ch, ch.lower()) for ch in text)


def strip_accents_preserve_case(text: str) -> str:
    """Strip Vietnamese accents while preserving original case.

    Args:
        text: Input text possibly containing Vietnamese accented characters.

    Returns:
        String with all accents stripped, keeping original casing.

    """
    return "".join(VIETNAMESE_ACCENT_MAP.get(ch, ch) for ch in text)


def strip_vietnamese_accents(text: str) -> str:
    """Alias for strip_accents(). Strip Vietnamese accents and return lowercase ASCII."""
    return strip_accents(text)


def to_no_tone_key(text: str) -> str:
    """Convert Vietnamese text to a stable lowercase no-tone lookup key.

    Strips all Vietnamese diacritics and tone marks, converts Đ/đ to d,
    and lowercases the result. This produces a repeatable key for
    accent-insensitive lexicon lookups.

    Examples:
        to_no_tone_key("đường") -> "duong"
        to_no_tone_key("ĐƯỜNG") -> "duong"
        to_no_tone_key("Sổ hồng") -> "so hong"

    """
    return strip_accents(text)
