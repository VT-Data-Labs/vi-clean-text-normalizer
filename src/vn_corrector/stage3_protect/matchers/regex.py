"""RegexMatcher — patterns supplied via config, not hardcoded."""

from __future__ import annotations

from re import compile as re_compile

from vn_corrector.common.types import Span, SpanType
from vn_corrector.stage3_protect.matchers.base import Matcher


def _is_ascii_only(text: str) -> bool:
    """Return True when *text* contains only ASCII characters."""
    return all(ord(ch) < 128 for ch in text)


class RegexMatcher(Matcher):
    """Matcher driven by a list of regex patterns.

    Parameters
    ----------
    name:
        Matcher name (used in ``source`` metadata on spans).
    priority:
        Higher values win during conflict resolution.
    span_type:
        The ``SpanType`` to assign to all detected spans.
    patterns:
        One or more regex strings.  Combined into a single compiled
        alternation pattern via ``|``.
    require_ascii:
        If True, skip matches that contain non-ASCII characters
        (used to avoid matching Vietnamese diacritics).
    """

    def __init__(
        self,
        name: str,
        priority: int,
        span_type: SpanType,
        patterns: list[str],
        *,
        require_ascii: bool = False,
    ) -> None:
        self.name = name
        self.priority = priority
        self.span_type = span_type
        self.require_ascii = require_ascii

        if not patterns:
            self._regex = None
        else:
            joined = "|".join(f"(?:{p})" for p in patterns)
            self._regex = re_compile(joined)

    def find(self, text: str) -> list[Span]:
        if self._regex is None:
            return []

        spans: list[Span] = []
        for m in self._regex.finditer(text):
            val = m.group()
            if self.require_ascii and not _is_ascii_only(val):
                continue
            spans.append(
                Span(
                    type=self.span_type,
                    start=m.start(),
                    end=m.end(),
                    value=val,
                    priority=self.priority,
                    source=f"regex:{self.name}",
                )
            )
        return spans
