"""OCR confusion map builder.

Consumes error → correction pairs (from OCR review logs or manual rules)
and produces entries suitable for the confusion index used during
candidate generation.
"""

from __future__ import annotations

from vn_corrector.common.types import (
    OcrConfusionEntry,
    Score,
)
from vn_corrector.lexicon.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class ConfusionBuilder(LexiconBuilder[OcrConfusionEntry]):
    """Builder for OCR confusion entries."""

    def __init__(self, default_confidence: float = 0.7) -> None:
        self._default_confidence = default_confidence

    def build(self, input_data: BuilderInput) -> BuilderOutput[OcrConfusionEntry]:
        """Build :class:`OcrConfusionEntry` objects from confusion data.

        Parameters
        ----------
        input_data:
            Data must be a ``list[dict]`` with ``noisy``, ``corrections``,
            and optionally ``confidence`` keys.

        Returns
        -------
        BuilderOutput[OcrConfusionEntry]
            A validated tuple of OCR confusion entries.
        """
        data = input_data.data
        if not isinstance(data, list):
            raise TypeError(f"Expected list[dict], got {type(data).__name__}")

        entries: list[OcrConfusionEntry] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            noisy = str(entry.get("noisy", ""))
            if not noisy:
                continue
            raw_corrections = entry.get("corrections", [])
            corrections: tuple[str, ...] = (
                tuple(str(c) for c in raw_corrections) if isinstance(raw_corrections, list) else ()
            )
            if not corrections:
                continue
            conf = float(entry.get("confidence", self._default_confidence))
            normalized_noisy = strip_accents(noisy)

            entries.append(
                OcrConfusionEntry(
                    entry_id=f"ocr/{noisy}",
                    noisy=noisy,
                    normalized_noisy=normalized_noisy,
                    corrections=corrections,
                    score=Score(confidence=conf),
                )
            )

        return BuilderOutput[OcrConfusionEntry](
            name=input_data.name,
            entries=tuple(entries),
        )

    def validate_output(self, entries: list[OcrConfusionEntry]) -> list[str]:
        """Validate OCR confusion entries.

        Checks:
        - All entries have a non-empty noisy field.
        - All entries have at least one correction.
        - All entries have confidence in [0, 1].
        """
        errors: list[str] = []
        for i, e in enumerate(entries):
            if not e.noisy:
                errors.append(f"[{i}] entry has empty noisy field")
            if not e.corrections:
                errors.append(f"[{i}] entry has no corrections")
            if not 0.0 <= e.score.confidence <= 1.0:
                errors.append(f"[{i}] confidence out of range: {e.score.confidence}")
        return errors
