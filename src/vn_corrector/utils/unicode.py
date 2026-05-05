"""Unicode utility functions for Vietnamese text processing."""


def is_vietnamese_char(ch: str) -> bool:
    """Check if a character is a Vietnamese letter (with diacritics).

    Covers all precomposed forms used in Vietnamese:
    - Latin Extended Additional (U+1EA0-U+1EF9): tone-marked vowels (hook/dot/combined)
    - Latin Extended-B: Ơ (U+01A0), ơ (U+01A1), Ư (U+01AF), ư (U+01B0)
    - Latin Extended-A: Đ (U+0110), đ (U+0111), Ă (U+0102), ă (U+0103),
      Ĩ (U+0128), ĩ (U+0129), Ũ (U+0168), ũ (U+0169)
    - Latin-1 Supplement: ÀÁÂÃ (U+00C0-U+00C3), ÈÉÊ (U+00C8-U+00CA),
      ÌÍ (U+00CC-U+00CD), ÒÓÔÕ (U+00D2-U+00D5), ÙÚ (U+00D9-U+00DA),
      Ý (U+00DD), and lowercase equivalents (U+00E0-U+00FD range)
    """
    codepoint = ord(ch)
    return (
        # Latin Extended Additional: combined diacritic + tone-marked vowels
        0x1EA0 <= codepoint <= 0x1EF9
        # Latin Extended-B: Ơ, ơ, Ư, ư
        or codepoint in (0x01A0, 0x01A1, 0x01AF, 0x01B0)
        # Latin Extended-A: Đ, đ, Ă, ă, Ĩ, ĩ, Ũ, ũ
        or codepoint in (0x0110, 0x0111, 0x0102, 0x0103, 0x0128, 0x0129, 0x0168, 0x0169)
        # Latin-1 Supplement: ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝ and lowercase
        or (0x00C0 <= codepoint <= 0x00DD)
        or (0x00E0 <= codepoint <= 0x00FD)
    )


def contains_vietnamese(text: str) -> bool:
    """Check if text contains any Vietnamese character."""
    return any(is_vietnamese_char(ch) for ch in text)
