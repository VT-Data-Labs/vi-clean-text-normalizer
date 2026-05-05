"""Canonical key normalisation for the Stage-2 lexicon system.

Every lexicon lookup **must** operate on a canonical key produced by
:func:`normalize_key`.  This guarantees that “Muỗng” and “muong” map
to the same key, making lookups deterministic and accent-insensitive.
"""

from __future__ import annotations

import re as _re

from vn_corrector.lexicon.accent_stripper import strip_accents

_WHITESPACE_RE = _re.compile(r"\s+")


def normalize_key(text: str) -> str:
    """Canonical key for all lexicon operations.

    **Invariant**::

        normalize_key("Muỗng") == normalize_key("muong")  # → "muong"

    Steps
    -----
    1. Lowercase (via :func:`strip_accents` which already lowercases).
    2. Strip all Vietnamese accents/tone marks.
    3. Normalise whitespace — collapse runs of whitespace to a single
       space, then strip leading/trailing whitespace.

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

    # strip_accents already lowercases and strips accents
    no_accents = strip_accents(text)
    # collapse whitespace
    return _WHITESPACE_RE.sub(" ", no_accents).strip()
