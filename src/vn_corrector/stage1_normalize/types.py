"""Data model for normalized documents."""

from dataclasses import dataclass, field


@dataclass
class NormalizedDocument:
    """Canonical representation of a normalized text document.

    Attributes:
        original_text: The raw input text before any normalization.
        normalized_text: The text after all normalization steps.
        steps_applied: Ordered list of step names that ran.
        stats: Aggregated statistics keyed by metric name
            (e.g. ``unicode_changes``, ``removed_control``,
            ``converted_spaces``).
    """

    original_text: str
    normalized_text: str
    steps_applied: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
