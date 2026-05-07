"""Stage 3 — Protected Token Detection (backward-compatible re-exports).

New code should import directly from ``vn_corrector.stage3_protect``.
"""

from __future__ import annotations

import pathlib

from vn_corrector.common.spans import ProtectedDocument
from vn_corrector.stage3_protect import Matcher, load_matchers
from vn_corrector.stage3_protect.engine import (
    PH_LEFT,
    PH_RIGHT,
    make_placeholder,
    mask,
    resolve_conflicts,
    restore,
)
from vn_corrector.stage3_protect.matchers.lexicon import LexiconMatcher
from vn_corrector.stage3_protect.matchers.regex import RegexMatcher

# Legacy class aliases for import compatibility.
URLMatcher = RegexMatcher
EmailMatcher = RegexMatcher
PhoneMatcher = RegexMatcher
PercentMatcher = RegexMatcher
MoneyMatcher = RegexMatcher
CodeMatcher = RegexMatcher
UnitMatcher = RegexMatcher
NumberMatcher = RegexMatcher
DateMatcher = RegexMatcher

_DEFAULT_MATCHERS: list[Matcher] | None = None


def _get_default_matchers() -> list[Matcher]:
    global _DEFAULT_MATCHERS
    if _DEFAULT_MATCHERS is None:
        config_dir = (
            pathlib.Path(__file__).resolve().parent.parent.parent / "resources" / "matchers"
        )
        _DEFAULT_MATCHERS = load_matchers(str(config_dir)) if config_dir.is_dir() else []
    return _DEFAULT_MATCHERS


def protect(text: str) -> ProtectedDocument:
    """Protect detected spans in *text* using the default matcher config."""
    from vn_corrector.stage3_protect.engine import protect as engine_protect

    return engine_protect(text, _get_default_matchers())


MATCHERS = _get_default_matchers()

__all__ = [
    "MATCHERS",
    "PH_LEFT",
    "PH_RIGHT",
    "CodeMatcher",
    "DateMatcher",
    "EmailMatcher",
    "LexiconMatcher",
    "Matcher",
    "MoneyMatcher",
    "NumberMatcher",
    "PercentMatcher",
    "PhoneMatcher",
    "RegexMatcher",
    "URLMatcher",
    "UnitMatcher",
    "load_matchers",
    "make_placeholder",
    "mask",
    "protect",
    "resolve_conflicts",
    "restore",
]
