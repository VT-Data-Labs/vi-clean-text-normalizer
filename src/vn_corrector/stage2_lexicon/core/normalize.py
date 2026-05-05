"""Canonical key normalisation for the Stage-2 lexicon system.

Every lexicon lookup **must** operate on a canonical key produced by
:func:`normalize_key`.  This guarantees that "Muỗng" and "muong" map
to the same key, making lookups deterministic and accent-insensitive.

The actual implementation lives in
:mod:`vn_corrector.stage1_normalize.char_normalizer` —
this module re-exports for backward compatibility.
"""

from vn_corrector.stage1_normalize import normalize_key

__all__ = ["normalize_key"]
