"""Whitespace normalization step.

Normalizes line endings and converts non-standard space characters
while preserving intentional whitespace structure (multiple spaces,
indentation, leading/trailing whitespace).
"""

import re

# Non-standard space characters to convert to regular space.
_NONSTANDARD_SPACE_RE = re.compile(
    "["
    + "".join(
        chr(cp)
        for cp in [
            0x00A0,  # NBSP
            0x1680,  # Ogham space mark
            0x2000,  # En quad
            0x2001,  # Em quad
            0x2002,  # En space
            0x2003,  # Em space
            0x2004,  # Three-per-em space
            0x2005,  # Four-per-em space
            0x2006,  # Six-per-em space
            0x2007,  # Figure space
            0x2008,  # Punctuation space
            0x2009,  # Thin space
            0x200A,  # Hair space
            0x202F,  # Narrow NBSP
            0x205F,  # Medium mathematical space
            0x3000,  # Ideographic space
        ]
    )
    + "]"
)


def normalize_whitespace(text: str) -> tuple[str, dict[str, int]]:
    r"""Normalize whitespace while preserving intentional structure.

    Rules:
    - Normalize line endings: CRLF -> LF, standalone CR -> LF.
    - Convert non-standard spaces -> regular space.
    - Do NOT collapse multiple spaces.
    - Do NOT trim leading/trailing whitespace.
    - Do NOT modify indentation.

    Returns:
        Tuple of (normalized_text, stats) where stats contains:
        - ``converted_spaces`` — non-standard space chars replaced.
        - ``normalized_linebreaks`` — CR/LF sequences normalized.

    """
    stats: dict[str, int] = {}

    stats["normalized_linebreaks"] = text.count("\r")

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    stats["converted_spaces"] = len(_NONSTANDARD_SPACE_RE.findall(text))
    text = _NONSTANDARD_SPACE_RE.sub(" ", text)

    return text, stats
