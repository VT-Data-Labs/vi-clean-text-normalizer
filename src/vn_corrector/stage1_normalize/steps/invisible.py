"""Invisible / control character removal step.

Removes non-printing, zero-width, bidi, and BOM characters while
preserving structural whitespace (\\n, \\r, \\t).
"""


def remove_invisible(text: str) -> tuple[str, dict[str, int]]:
    """Remove invisible and non-printing control characters.

    Returns:
        Tuple of (cleaned_text, stats) where stats contains:
        - ``removed_control`` — C0 control chars removed.
        - ``removed_zero_width`` — zero-width / invisible operators.
        - ``removed_bidi`` — bidi override chars.
        - ``removed_bom`` — BOM / byte-order marks.

    """
    stats: dict[str, int] = {
        "removed_control": 0,
        "removed_zero_width": 0,
        "removed_bidi": 0,
        "removed_bom": 0,
    }

    chars: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp <= 0x08 or 0x0E <= cp <= 0x1F or cp == 0x7F or cp == 0x0B or cp == 0x0C:
            stats["removed_control"] += 1
        elif cp == 0x00AD:
            stats["removed_control"] += 1  # soft hyphen
        elif 0x200B <= cp <= 0x200F:
            stats["removed_zero_width"] += 1
        elif 0x202A <= cp <= 0x202E:
            stats["removed_bidi"] += 1
        elif cp == 0x2028 or cp == 0x2029:
            stats["removed_control"] += 1  # line/para separator
        elif 0x2060 <= cp <= 0x2064:
            stats["removed_zero_width"] += 1
        elif cp == 0xFEFF:
            stats["removed_bom"] += 1
        elif cp == 0x061C:
            stats["removed_bidi"] += 1  # arabic letter mark
        else:
            chars.append(ch)

    return "".join(chars), stats
