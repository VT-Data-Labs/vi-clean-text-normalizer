"""Stage 0 + Stage 1: Input Normalization and Unicode Normalization.

Backward-compatible re-exports. The actual implementation lives in
the :mod:`~vn_corrector.stage1_normalize` package.

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

from vn_corrector.stage1_normalize.engine import normalize as _pipeline
from vn_corrector.stage1_normalize.steps.invisible import remove_invisible as _rm_invisible
from vn_corrector.stage1_normalize.steps.unicode import normalize_unicode as _unicode
from vn_corrector.stage1_normalize.steps.whitespace import normalize_whitespace as _whitespace


def normalize(text: str) -> str:
    """Apply the full normalization pipeline.

    Returns the normalized text only (``str``).  For full observability
    (stats, steps applied), use
    :func:`vn_corrector.stage1_normalize.engine.normalize` which returns
    a :class:`~vn_corrector.stage1_normalize.types.NormalizedDocument`.

    Steps:
    1. Unicode NFC normalization.
    2. Remove invisible/control characters.
    3. Normalize whitespace (line endings, non-standard spaces).
    """
    return _pipeline(text).normalized_text


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to NFC (Canonical Composition).

    NFC composes decomposed characters (NFD/NFKD) into their canonical
    precomposed forms, which is the standard for Vietnamese text.
    """
    return _unicode(text)[0]


def remove_invisible_characters(text: str) -> str:
    """Remove invisible and non-printing control characters.

    Preserves:
    - \\n (newline), \\r (carriage return), \\t (tab)
    - Printable characters including Vietnamese letters
    - Normal punctuation and symbols
    """
    return _rm_invisible(text)[0]


def normalize_whitespace(text: str) -> str:
    r"""Normalize whitespace while preserving intentional newlines.

    - Converts non-standard spaces (NBSP, thin space, etc.) to regular space.
    - Normalizes line endings: \\r\\n → \\n, standalone \\r → \\n.
    - Does NOT collapse multiple spaces (preserves formatting).
    - Does NOT trim leading/trailing whitespace.
    """
    return _whitespace(text)[0]
