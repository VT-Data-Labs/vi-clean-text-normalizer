"""Abbreviation lexicon builder.

Consumes abbreviation → expansion(s) rules and produces
:class:`~vn_corrector.common.types.AbbreviationEntry` objects.
"""

from __future__ import annotations

from vn_corrector.common.lexicon import AbbreviationEntry, Provenance
from vn_corrector.common.scoring import Score
from vn_corrector.stage2_lexicon.builders.base import LexiconBuilder
from vn_corrector.stage2_lexicon.core.types import BuilderInput, BuilderOutput


class AbbreviationBuilder(LexiconBuilder[AbbreviationEntry]):
    """Builder for abbreviation entries."""

    def __init__(self, default_confidence: float = 1.0) -> None:
        self._default_confidence = default_confidence

    def build(self, input_data: BuilderInput) -> BuilderOutput[AbbreviationEntry]:
        """Build :class:`AbbreviationEntry` objects from abbreviation data.

        Parameters
        ----------
        input_data:
            Data must be a ``list[dict]`` with ``abbreviation``,
            ``expansions``, and optionally ``normalized``, ``tags`` keys.

        Returns
        -------
        BuilderOutput[AbbreviationEntry]
            A validated tuple of abbreviation entries.
        """
        data = input_data.data
        if not isinstance(data, list):
            raise TypeError(f"Expected list[dict], got {type(data).__name__}")

        entries: list[AbbreviationEntry] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            abbrev = str(entry.get("abbreviation", ""))
            if not abbrev:
                continue
            raw_exps = entry.get("expansions", [])
            expansions = tuple(str(e) for e in raw_exps) if isinstance(raw_exps, list) else ()
            if not expansions:
                continue
            normalized = str(entry.get("normalized", abbrev.lower()))
            raw_tags = entry.get("tags")
            tags = tuple(raw_tags) if isinstance(raw_tags, list) else ()
            ambiguous = entry.get("ambiguous", len(expansions) > 1)
            if not isinstance(ambiguous, bool):
                ambiguous = len(expansions) > 1

            entries.append(
                AbbreviationEntry(
                    entry_id=f"abbrev/{abbrev}",
                    surface=abbrev,
                    normalized=normalized,
                    expansions=expansions,
                    score=Score(confidence=self._default_confidence),
                    provenance=Provenance(
                        source=input_data.source,
                        version=input_data.version,
                    ),
                    ambiguous=ambiguous,
                    tags=tags,
                )
            )

        return BuilderOutput[AbbreviationEntry](
            name=input_data.name,
            entries=tuple(entries),
        )

    def validate_output(self, entries: list[AbbreviationEntry]) -> list[str]:
        """Validate abbreviation entries.

        Checks:
        - All entries have a non-empty surface.
        - All entries have at least one expansion.
        - All expansions are non-empty strings.
        """
        errors: list[str] = []
        for i, e in enumerate(entries):
            if not e.surface:
                errors.append(f"[{i}] entry has empty surface")
            if not e.expansions:
                errors.append(f"[{i}] entry has no expansions")
            for j, exp in enumerate(e.expansions):
                if not exp:
                    errors.append(f"[{i}] expansion [{j}] is empty")
        return errors
