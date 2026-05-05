"""Backward-compat shim — canonical logic moved to ``vn_corrector.stage1_normalize``.

All Vietnamese accent stripping and character normalisation now lives in
:mod:`vn_corrector.stage1_normalize.char_normalizer`.

New code **must** import from ``vn_corrector.stage1_normalize`` directly.
"""

from vn_corrector.stage1_normalize import (
    VIETNAMESE_ACCENT_MAP,
    strip_accents,
    strip_accents_preserve_case,
    strip_vietnamese_accents,
    to_no_tone_key,
)

__all__ = [
    "VIETNAMESE_ACCENT_MAP",
    "strip_accents",
    "strip_accents_preserve_case",
    "strip_vietnamese_accents",
    "to_no_tone_key",
]
