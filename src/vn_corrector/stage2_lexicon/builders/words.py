"""Word lexicon builder.

Consumes raw word lists and produces ``surface → metadata`` entries
for known multi-syllable Vietnamese words, foreign terms, and
domain-specific vocabulary.
"""

from __future__ import annotations

from vn_corrector.common.enums import LexiconKind
from vn_corrector.common.lexicon import LexiconEntry, Provenance
from vn_corrector.common.scoring import Score
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.core.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class WordBuilder(LexiconBuilder[LexiconEntry]):
    """Builder for word/unit lexicon entries."""

    def __init__(self, default_freq: float = 1.0) -> None:
        self._default_freq = default_freq

    def build(self, input_data: BuilderInput) -> BuilderOutput[LexiconEntry]:
        """Build :class:`LexiconEntry` objects from word data.

        Parameters
        ----------
        input_data:
            Data must be a ``list[dict]`` with ``surface`` and optionally
            ``type``, ``freq``, and ``domain`` keys.

        Returns
        -------
        BuilderOutput[LexiconEntry]
            A validated tuple of word entries.
        """
        data = input_data.data
        if not isinstance(data, list):
            raise TypeError(f"Expected list[dict], got {type(data).__name__}")

        entries: list[LexiconEntry] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            surface = str(entry.get("surface", ""))
            if not surface:
                continue
            freq = float(entry.get("freq", self._default_freq))
            entry_type = str(entry.get("type", "word"))
            raw_domain = entry.get("domain")
            domain = str(raw_domain) if raw_domain is not None else None
            no_tone = strip_accents(surface)

            entries.append(
                LexiconEntry(
                    entry_id=f"word/{surface}",
                    surface=surface,
                    normalized=surface.lower(),
                    no_tone=no_tone,
                    kind=self._infer_kind(entry_type),
                    score=Score(confidence=freq, frequency=freq),
                    provenance=Provenance(
                        source=input_data.source,
                        version=input_data.version,
                    ),
                    domain=domain,
                    tags=(entry_type,),
                )
            )

        return BuilderOutput[LexiconEntry](
            name=input_data.name,
            entries=tuple(entries),
        )

    def validate_output(self, entries: list[LexiconEntry]) -> list[str]:
        """Validate word entries.

        Checks:
        - All entries have a non-empty surface.
        - All entries have a non-empty no_tone key.
        - All entries have non-negative frequency.
        """
        errors: list[str] = []
        for i, e in enumerate(entries):
            if not e.surface:
                errors.append(f"[{i}] entry has empty surface")
            if not e.no_tone:
                errors.append(f"[{i}] entry has empty no_tone key")
            if e.score.frequency < 0:
                errors.append(f"[{i}] negative frequency {e.score.frequency}")
        return errors

    @staticmethod
    def _infer_kind(entry_type: str) -> LexiconKind:
        kind_map: dict[str, LexiconKind] = {
            "common_word": LexiconKind.WORD,
            "unit_word": LexiconKind.UNIT,
            "chemical": LexiconKind.DOMAIN_TERM,
            "brand": LexiconKind.BRAND,
        }
        return kind_map.get(entry_type, LexiconKind.WORD)
