"""Phrase / n-gram lexicon builder.

Consumes raw text corpora and produces phrase entries with n-gram
frequencies.  Critical for context-aware correction (M5 integration):
phrases like "số muỗng gạt ngang" disambiguate syllable candidates.
"""

from __future__ import annotations

from typing import Any

from vn_corrector.common.types import (
    PhraseEntry,
    Provenance,
    Score,
)
from vn_corrector.lexicon.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class PhraseBuilder(LexiconBuilder):
    """Builder for phrase (n-gram) entries."""

    def __init__(self, default_freq: float = 0.5) -> None:
        self._default_freq = default_freq

    def build(self, input_data: BuilderInput) -> BuilderOutput:
        """Build :class:`PhraseEntry` objects from phrase data.

        Parameters
        ----------
        input_data:
            Data must be a ``list[dict]`` with ``phrase``, ``n``, and
            optionally ``freq``, ``domain``, and ``tags`` keys.

        Returns
        -------
        BuilderOutput
            A validated tuple of phrase entries.
        """
        data = input_data.data
        if not isinstance(data, list):
            raise TypeError(f"Expected list[dict], got {type(data).__name__}")

        entries: list[PhraseEntry] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            phrase = str(entry.get("phrase", ""))
            if not phrase:
                continue
            n_raw = entry.get("n", 0)
            n = int(n_raw) if isinstance(n_raw, (int, float)) else 0
            freq = float(entry.get("freq", self._default_freq))
            raw_domain = entry.get("domain")
            domain = str(raw_domain) if raw_domain is not None else None
            raw_tags = entry.get("tags")
            tags = tuple(raw_tags) if isinstance(raw_tags, list) else ()
            no_tone = strip_accents(phrase)

            entries.append(
                PhraseEntry(
                    entry_id=f"phrase/{phrase}",
                    phrase=phrase,
                    normalized=no_tone,
                    no_tone=no_tone,
                    n=n,
                    score=Score(confidence=freq, frequency=freq),
                    provenance=Provenance(
                        source=input_data.source,
                        version=input_data.version,
                    ),
                    domain=domain,
                    tags=tags,
                )
            )

        return BuilderOutput(
            name=input_data.name,
            entries=tuple(entries),
        )

    def validate_output(self, entries: list[Any]) -> list[str]:
        """Validate phrase entries.

        Checks:
        - All entries have a non-empty phrase.
        - All entries have n >= 1.
        - All entries have non-negative frequency.
        """
        errors: list[str] = []
        for i, e in enumerate(entries):
            if not e.phrase:
                errors.append(f"[{i}] entry has empty phrase")
            if e.n < 1:
                errors.append(f"[{i}] n must be >= 1, got {e.n}")
            if e.score.frequency < 0:
                errors.append(f"[{i}] negative frequency {e.score.frequency}")
        return errors
