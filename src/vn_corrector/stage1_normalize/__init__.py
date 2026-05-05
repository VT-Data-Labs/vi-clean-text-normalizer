"""Stage 1: Input and Unicode Normalization.

This package defines the canonical text representation
used by all downstream stages.

Public API
----------
- :func:`char_normalizer.strip_accents` — accent stripping (lowercased)
- :func:`char_normalizer.strip_accents_preserve_case` — accent stripping (case-preserving)
- :func:`char_normalizer.strip_vietnamese_accents` — alias for *strip_accents*
- :func:`char_normalizer.to_no_tone_key` — stable no-tone key
- :func:`char_normalizer.normalize_text` — NFC + fix_lookalikes + lowercase
- :func:`char_normalizer.normalize_key` — canonical lexicon key
- :func:`char_normalizer.fix_lookalikes` — Unicode lookalike correction
- :func:`engine.normalize` — full pipeline normalisation
- :const:`char_normalizer.VIETNAMESE_ACCENT_MAP` — codepoint → base letter map
"""

from vn_corrector.stage1_normalize.char_normalizer import (
    VIETNAMESE_ACCENT_MAP,
    fix_lookalikes,
    normalize_key,
    normalize_text,
    strip_accents,
    strip_accents_preserve_case,
    strip_vietnamese_accents,
    to_no_tone_key,
)

__all__ = [
    "VIETNAMESE_ACCENT_MAP",
    "fix_lookalikes",
    "normalize_key",
    "normalize_text",
    "strip_accents",
    "strip_accents_preserve_case",
    "strip_vietnamese_accents",
    "to_no_tone_key",
]
