"""Syllable lexicon builder.

Consumes raw word lists / syllable corpora and produces
``base → [accented forms]`` entries suitable for diacritic
restoration during correction.

Input format
------------
A list of dictionaries with keys ``base``, ``forms``, and optionally ``freq``::

    [
      {"base": "muong", "forms": ["muỗng", "mường"], "freq": {"muỗng": 0.91, "mường": 0.05}},
      ...
    ]
"""

from __future__ import annotations

from vn_corrector.common.enums import LexiconKind, LexiconSource
from vn_corrector.common.scoring import Score
from vn_corrector.lexicon.types import LexiconEntry, Provenance
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class SyllableBuilder(LexiconBuilder[LexiconEntry]):
    """Builder for syllable entries (base → accented forms)."""

    def __init__(self, default_confidence: float = 0.5) -> None:
        self._default_confidence = default_confidence

    def build(self, input_data: BuilderInput) -> BuilderOutput[LexiconEntry]:
        """Build :class:`LexiconEntry` objects from syllable data.

        Parameters
        ----------
        input_data:
            Data must be a ``list[dict]`` with ``base``, ``forms``, and
            optional ``freq`` keys.

        Returns
        -------
        BuilderOutput[LexiconEntry]
            A validated tuple of syllable entries.
        """
        data = input_data.data
        if not isinstance(data, list):
            raise TypeError(f"Expected list[dict], got {type(data).__name__}")

        entries: list[LexiconEntry] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            base = str(entry.get("base", ""))
            raw_forms = entry.get("forms", [])
            forms: list[str] = [str(f) for f in raw_forms] if isinstance(raw_forms, list) else []
            freq_map: dict[str, float] = {}
            raw_freq = entry.get("freq")
            if isinstance(raw_freq, dict):
                freq_map = {str(k): float(v) for k, v in raw_freq.items()}

            for form in forms:
                conf = freq_map.get(form, self._default_confidence)
                entries.append(
                    LexiconEntry(
                        entry_id=f"syllable/{form}",
                        surface=form,
                        normalized=form,
                        no_tone=base,
                        kind=LexiconKind.SYLLABLE,
                        score=Score(confidence=conf, frequency=conf),
                        provenance=Provenance(
                            source=LexiconSource.CORPUS
                            if input_data.source == LexiconSource.CORPUS
                            else LexiconSource.BUILT_IN,
                            version=input_data.version,
                        ),
                        tags=("syllable",),
                    )
                )

        return BuilderOutput[LexiconEntry](
            name=input_data.name,
            entries=tuple(entries),
        )

    def validate_output(self, entries: list[LexiconEntry]) -> list[str]:
        """Validate syllable entries.

        Checks:
        - All entries have a non-empty surface.
        - All entries have a non-empty no_tone key.
        - All entries have kind == SYLLABLE.
        """
        errors: list[str] = []
        for i, e in enumerate(entries):
            if not e.surface:
                errors.append(f"[{i}] entry has empty surface")
            if not e.no_tone:
                errors.append(f"[{i}] entry has empty no_tone key")
            if e.kind != LexiconKind.SYLLABLE:
                errors.append(f"[{i}] expected SYLLABLE, got {e.kind}")
        return errors
