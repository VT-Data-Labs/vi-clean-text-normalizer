"""Abstract base class for all matchers in the protected token rule engine."""

from __future__ import annotations

from abc import ABC, abstractmethod

from vn_corrector.common.spans import ProtectedSpan


class Matcher(ABC):
    """A detect-and-report matcher for a specific span type.

    Subclasses set *name*, *priority*, and *span_type* as instance
    attributes (typically in ``__init__``) and implement ``find(text)``
    to yield detected spans.  Higher priority values win during conflict
    resolution.
    """

    name: str = ""
    priority: int = 0

    @abstractmethod
    def find(self, text: str) -> list[ProtectedSpan]:
        """Return all detected spans of this type in *text*."""
