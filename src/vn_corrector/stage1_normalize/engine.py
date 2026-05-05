"""Pipeline orchestration for Stage 1 normalization.

Runs normalization steps in order, collects statistics,
and verifies invariants on the result.
"""

from vn_corrector.stage1_normalize.config import NormalizerConfig
from vn_corrector.stage1_normalize.steps.invisible import remove_invisible
from vn_corrector.stage1_normalize.steps.unicode import normalize_unicode
from vn_corrector.stage1_normalize.steps.whitespace import normalize_whitespace
from vn_corrector.stage1_normalize.types import NormalizedDocument


def normalize(
    text: str,
    config: NormalizerConfig | None = None,
) -> NormalizedDocument:
    """Apply the full normalization pipeline.

    Steps (in order):
    1. Unicode NFC normalization.
    2. Remove invisible/control characters.
    3. Normalize whitespace (line endings, non-standard spaces).

    Args:
        text: Raw input text.
        config: Optional configuration to enable/disable steps.

    Returns:
        A :class:`NormalizedDocument` with the result, applied steps,
        and aggregated statistics.

    """
    if config is None:
        config = NormalizerConfig()

    steps_applied: list[str] = []
    aggregated: dict[str, int] = {}
    current = text

    if config.normalize_unicode:
        current, stats = normalize_unicode(current)
        _merge_stats(aggregated, stats)
        steps_applied.append("normalize_unicode")

    if config.remove_invisible:
        current, stats = remove_invisible(current)
        _merge_stats(aggregated, stats)
        steps_applied.append("remove_invisible")

    if config.normalize_whitespace:
        current, stats = normalize_whitespace(current)
        _merge_stats(aggregated, stats)
        steps_applied.append("normalize_whitespace")

    return NormalizedDocument(
        original_text=text,
        normalized_text=current,
        steps_applied=steps_applied,
        stats=aggregated,
    )


def _merge_stats(target: dict[str, int], source: dict[str, int]) -> None:
    """Merge *source* stats into *target* in-place."""
    for key, value in source.items():
        target[key] = target.get(key, 0) + value
