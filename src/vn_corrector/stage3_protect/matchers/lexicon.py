"""LexiconMatcher — matches entries from an external word list."""

from __future__ import annotations

from re import IGNORECASE
from re import compile as re_compile

from vn_corrector.common.enums import SpanType
from vn_corrector.common.spans import ProtectedSpan
from vn_corrector.stage3_protect.matchers.base import Matcher


class LexiconMatcher(Matcher):
    """Matcher that finds lexicon entries in the input text.

    Builds a single compiled alternation regex from the lexicon set
    so that matching is O(n) per input character rather than O(m·n)
    in the number of lexicon entries.

    Parameters
    ----------
    name:
        Matcher name (used in ``source`` metadata on spans).
    priority:
        Higher values win during conflict resolution.
    span_type:
        The ``SpanType`` to assign to all matched spans.
    lexicon:
        Set of entry strings to look for.
    case_sensitive:
        If False, matching is case-insensitive.
    """

    def __init__(
        self,
        name: str,
        priority: int,
        span_type: SpanType,
        lexicon: set[str],
        *,
        case_sensitive: bool = True,
    ) -> None:
        self.name = name
        self.priority = priority
        self.span_type = span_type

        if not lexicon:
            self._regex = None
            return

        # Sort longest-first so alternation prefers longer matches.
        sorted_entries = sorted(lexicon, key=lambda e: (-len(e), e))

        flags = 0 if case_sensitive else IGNORECASE
        pattern = "|".join(self._wrap(e) for e in sorted_entries)
        self._regex = re_compile(pattern, flags)

    @staticmethod
    def _wrap(entry: str) -> str:
        """Wrap an entry with word-boundary anchors when safe.

        Pure-alphanumeric entries get ``\\b`` anchors so that matching
        ``DHA`` does not match inside ``DHAP``.  Entries with non-word
        characters (dashes, primes, etc.) are matched literally.
        """
        if entry.isalnum():
            return f"\\b{re_compile(entry).pattern}\\b"
        return re_compile(entry).pattern

    def find(self, text: str) -> list[ProtectedSpan]:
        if self._regex is None:
            return []

        return [
            ProtectedSpan(
                type=self.span_type,
                start=m.start(),
                end=m.end(),
                value=m.group(),
                priority=self.priority,
                source=f"lexicon:{self.name}",
            )
            for m in self._regex.finditer(text)
        ]

    @staticmethod
    def load_from_file(path: str, encoding: str = "utf-8") -> set[str]:
        """Load lexicon entries from a text file (one entry per line).

        Empty lines and lines starting with ``#`` are ignored.
        """
        entries: set[str] = set()
        with open(path, encoding=encoding) as fh:
            for line in fh:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    entries.add(stripped)
        return entries
