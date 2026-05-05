"""Lexicon store for Vietnamese correction pipeline.

Provides in-memory storage and lookup for syllables, words, units,
abbreviations, and foreign terms loaded from built-in JSON resources.
"""

from __future__ import annotations

import json
from importlib.resources import files as resource_files
from pathlib import Path

from vn_corrector.common.types import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconLookupResult,
)
from vn_corrector.lexicon.accent_stripper import strip_accents

_RESOURCE_DIR = "resources" / Path("lexicons")


def _resource_path(filename: str) -> Path:
    """Get the filesystem path to a built-in lexicon resource."""
    return resource_files("vn_corrector").joinpath(_RESOURCE_DIR, filename)  # type: ignore[return-value]


def _load_json(filename: str) -> list[dict[str, object]] | dict[str, object]:
    """Load and parse a JSON resource file."""
    path = _resource_path(filename)
    with path.open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


class LexiconStore:
    """In-memory store for Vietnamese lexicon data.

    Stores syllables indexed by accentless normalized form, words and
    units by surface form, abbreviations with multiple expansions, and
    foreign terms for quick membership checks.  Later entries with the
    same normalized key are appended, not overwritten.
    """

    def __init__(self) -> None:
        # normalized (accentless) -> syllable entries
        self._syllable_index: dict[str, list[LexiconEntry]] = {}
        # surface form -> syllable entries (for exact lookup)
        self._syllable_by_surface: dict[str, list[LexiconEntry]] = {}
        # normalized (accentless) -> word entries
        self._word_index: dict[str, list[LexiconEntry]] = {}
        # surface form -> word entries (for exact lookup)
        self._word_by_surface: dict[str, LexiconEntry] = {}
        # abbreviation -> expansion list
        self._abbreviations: dict[str, list[str]] = {}
        # abbreviation -> AbbreviationEntry
        self._abbrev_entries: dict[str, AbbreviationEntry] = {}
        # foreign terms set
        self._foreign_words: set[str] = set()
        # All surface forms for quick combined contains check
        self._word_surfaces: set[str] = set()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def load_default(cls) -> LexiconStore:
        """Load all built-in lexicon resources and return a new store."""
        store = cls()
        store._load_syllables()
        store._load_words()
        store._load_units()
        store._load_abbreviations()
        store._load_foreign_words()
        return store

    def _load_syllables(self) -> None:
        data: list[dict[str, object]] = _load_json("syllables.vi.json")  # type: ignore[assignment]
        for entry in data:
            base = str(entry["base"])
            raw_forms = entry["forms"]
            forms: list[str] = [str(f) for f in raw_forms] if isinstance(raw_forms, list) else []
            freq_map: dict[str, float] = {}
            raw_freq = entry.get("freq")
            if isinstance(raw_freq, dict):
                freq_map = {str(k): float(v) for k, v in raw_freq.items()}

            for form in forms:
                lexicon_entry = LexiconEntry(
                    surface=form,
                    normalized=base,
                    no_tone=base,
                    kind="syllable",
                    source="built-in",
                    confidence=freq_map.get(form, 0.5),
                    frequency=freq_map.get(form, 0.0),
                    tags=["syllable"],
                )
                # Index by normalized (accentless) key
                if base not in self._syllable_index:
                    self._syllable_index[base] = []
                self._syllable_index[base].append(lexicon_entry)

                # Index by surface for exact lookup
                if form not in self._syllable_by_surface:
                    self._syllable_by_surface[form] = []
                self._syllable_by_surface[form].append(lexicon_entry)

    def _load_words(self) -> None:
        data: list[dict[str, object]] = _load_json("words.vi.json")  # type: ignore[assignment]
        for entry in data:
            surface = str(entry["surface"])
            normalized = str(entry["normalized"])
            freq = float(entry.get("freq", 1.0))  # type: ignore[arg-type]
            entry_type = str(entry.get("type", "word"))
            raw_domain = entry.get("domain")
            domain = str(raw_domain) if raw_domain is not None else None
            lexicon_entry = LexiconEntry(
                surface=surface,
                normalized=normalized,
                no_tone=normalized,
                kind=entry_type,
                source="built-in",
                confidence=freq,
                frequency=freq,
                domain=domain,
                tags=[entry_type],
            )
            self._word_by_surface[surface] = lexicon_entry
            self._word_surfaces.add(surface)
            if normalized not in self._word_index:
                self._word_index[normalized] = []
            self._word_index[normalized].append(lexicon_entry)

    def _load_units(self) -> None:
        data: list[dict[str, object]] = _load_json("units.vi.json")  # type: ignore[assignment]
        for entry in data:
            surface = str(entry["surface"])
            normalized = str(entry["normalized"])
            freq = float(entry.get("freq", 1.0))  # type: ignore[arg-type]
            raw_domain = entry.get("domain", "measurement")
            domain = str(raw_domain) if raw_domain is not None else "measurement"
            lexicon_entry = LexiconEntry(
                surface=surface,
                normalized=normalized,
                no_tone=normalized,
                kind="unit",
                source="built-in",
                confidence=freq,
                frequency=freq,
                domain=domain,
                tags=["unit"],
            )
            self._word_by_surface[surface] = lexicon_entry
            self._word_surfaces.add(surface)
            if normalized not in self._word_index:
                self._word_index[normalized] = []
            self._word_index[normalized].append(lexicon_entry)

    def _load_abbreviations(self) -> None:
        data: list[dict[str, object]] = _load_json("abbreviations.vi.json")  # type: ignore[assignment]
        for entry in data:
            abbrev = str(entry["abbreviation"])
            raw_exps = entry["expansions"]
            expansions: list[str] = [str(e) for e in raw_exps] if isinstance(raw_exps, list) else []
            normalized = str(entry.get("normalized", abbrev.lower()))
            self._abbreviations[abbrev] = expansions
            self._abbrev_entries[abbrev] = AbbreviationEntry(
                surface=abbrev,
                normalized=normalized,
                expansions=expansions,
                source="built-in",
                confidence=1.0,
                ambiguous=len(expansions) > 1,
            )

    def _load_foreign_words(self) -> None:
        raw_data = _load_json("foreign_words.json")
        if isinstance(raw_data, list):
            self._foreign_words = {str(item) for item in raw_data}

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up text by exact surface form across syllables and words."""
        entries: list[LexiconEntry | AbbreviationEntry] = []

        # Check syllable surfaces
        if text in self._syllable_by_surface:
            entries.extend(self._syllable_by_surface[text])

        # Check word surfaces
        if text in self._word_by_surface:
            entries.append(self._word_by_surface[text])

        return LexiconLookupResult(
            found=bool(entries),
            entries=entries,
        )

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up by accentless normalized form (syllables and words)."""
        key = strip_accents(text).lower()
        entries: list[LexiconEntry | AbbreviationEntry] = []

        # Check syllable index
        if key in self._syllable_index:
            entries.extend(self._syllable_index[key])

        # Check word index
        if key in self._word_index:
            entries.extend(self._word_index[key])

        return LexiconLookupResult(
            found=bool(entries),
            entries=entries,
        )

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up abbreviation expansions."""
        entry = self._abbrev_entries.get(text)
        return LexiconLookupResult(
            found=entry is not None,
            entries=[entry] if entry is not None else [],
        )

    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        """Look up by no-tone key (alias for lookup_accentless)."""
        return self.lookup_accentless(text)

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return all syllable entries matching a no-tone key.

        Args:
            no_tone_key: The accentless lookup key (e.g. \"muong\").

        Returns:
            List of matching syllable LexiconEntry objects.
        """
        return list(self._syllable_index.get(no_tone_key, []))

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        """Check if text is a known word (surface form match)."""
        return text in self._word_surfaces

    def contains_syllable(self, text: str) -> bool:
        """Check if text is a known syllable (surface form match)."""
        return text in self._syllable_by_surface

    def contains_foreign_word(self, text: str) -> bool:
        """Check if text is in the foreign words list."""
        return text in self._foreign_words

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        """Return all abbreviation entries."""
        return list(self._abbrev_entries.values())

    def get_abbreviation_count(self) -> int:
        """Return the number of abbreviation entries."""
        return len(self._abbreviations)
