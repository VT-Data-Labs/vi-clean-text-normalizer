"""Stage 3 — Protected Token Detection (configurable rule engine).

Public API:
    protect(text, matchers=None)  -> ProtectedDocument
    mask(text, spans)             -> (masked_text, placeholder_map)
    restore(masked_text, pmap)    -> original_text
    load_matchers(config_dir)     -> list[Matcher]
"""

from vn_corrector.stage3_protect.engine import mask, protect, restore
from vn_corrector.stage3_protect.matchers.base import Matcher
from vn_corrector.stage3_protect.matchers.lexicon import LexiconMatcher
from vn_corrector.stage3_protect.matchers.regex import RegexMatcher
from vn_corrector.stage3_protect.registry import load_matchers

__all__ = [
    "LexiconMatcher",
    "Matcher",
    "RegexMatcher",
    "load_matchers",
    "mask",
    "protect",
    "restore",
]
