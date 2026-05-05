"""Lexicon store interface and JSON-backed implementation.

Provides:
- :class:`LexiconStore` — abstract base class for all lexicon backends.
- :class:`JsonLexiconStore` — in-memory store loaded from built-in JSON resources.
- :func:`load_default_lexicon` — convenience to load the default built-in lexicon.
- :func:`load_json_resource` — load a raw JSON resource file from package data.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from importlib.resources import files as resource_files
from pathlib import Path
from typing import cast

from vn_corrector.common.types import (
    AbbreviationEntry,
    Candidate,
    CandidateSource,
    LexiconEntry,
    LexiconKind,
    LexiconLookupResult,
    LexiconSource,
    OcrConfusionEntry,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
    Score,
)
from vn_corrector.lexicon.accent_stripper import strip_accents

_RESOURCE_DIR = "resources" / Path("lexicons")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resource_path(filename: str) -> Path:
    """Return the filesystem path to a built-in lexicon resource file."""
    return cast(Path, resource_files("vn_corrector").joinpath(_RESOURCE_DIR, filename))


def load_json_resource(filename: str) -> list[dict[str, object]] | dict[str, object]:
    """Load and parse a JSON resource file from the package's built-in resources."""
    path = resource_path(filename)
    with path.open(encoding="utf-8") as f:
        return cast("list[dict[str, object]] | dict[str, object]", json.load(f))


# Backward-compat alias — kept for external consumers that imported the private name.
_load_json = load_json_resource


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class LexiconStore(ABC):
    """Abstract interface for a Vietnamese lexicon store.

    All backends (:class:`JsonLexiconStore`, :class:`SqliteLexiconStore`, …)
    must implement this interface.  Lookups are read-only; data is populated
    by each backend at construction time.
    """

    # -- Surface / exact lookups -------------------------------------------

    @abstractmethod
    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up *text* by exact surface form (syllables, words, abbreviations)."""

    @abstractmethod
    def lookup_syllable(self, text: str) -> list[str]:
        """Return syllable candidate surfaces for *text* (accent-insensitive)."""

    @abstractmethod
    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        """Return unit entries whose surface exactly matches *text*."""

    @abstractmethod
    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up an abbreviation by its surface form."""

    @abstractmethod
    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by exact surface form."""

    @abstractmethod
    def lookup_phrase_str(self, text: str) -> str | None:
        """Look up a phrase by its no-tone form, return the accented surface or ``None``."""

    # -- Accentless / no-tone lookups --------------------------------------

    @abstractmethod
    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up *text* by stripped/accentless form (syllables + words)."""

    @abstractmethod
    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        """Alias for :meth:`lookup_accentless`."""

    @abstractmethod
    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by no-tone (accentless) form."""

    @abstractmethod
    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return all syllable entries matching a no-tone key."""

    # -- OCR confusion -----------------------------------------------------

    @abstractmethod
    def lookup_ocr(self, noisy: str) -> list[str]:
        """Return known correction surfaces for a noisy OCR token."""

    @abstractmethod
    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        """Get known corrections for a noisy OCR token as structured result."""

    @abstractmethod
    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        """Return the full OCR confusion map (noisy → correction surfaces)."""

    # -- Membership --------------------------------------------------------

    @abstractmethod
    def contains_word(self, text: str) -> bool:
        """Return ``True`` if *text* is a known word or unit (exact surface)."""

    @abstractmethod
    def contains_syllable(self, text: str) -> bool:
        """Return ``True`` if *text* is a known syllable (exact surface)."""

    @abstractmethod
    def contains_foreign_word(self, text: str) -> bool:
        """Return ``True`` if *text* is in the foreign-word list."""

    # -- Aggregate / statistics --------------------------------------------

    @abstractmethod
    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        """Return all abbreviation entries."""

    @abstractmethod
    def get_abbreviation_count(self) -> int:
        """Return the number of abbreviation entries."""

    @abstractmethod
    def get_phrase_count(self) -> int:
        """Return the number of unique phrase no-tone keys."""

    @abstractmethod
    def get_ocr_confusion_count(self) -> int:
        """Return the number of OCR confusion entries."""

    @abstractmethod
    def get_syllable_entry_count(self) -> int:
        """Return the total number of individual syllable entries."""

    @abstractmethod
    def get_word_count(self) -> int:
        """Return the number of known word/unit surface forms."""

    @abstractmethod
    def get_foreign_word_count(self) -> int:
        """Return the number of foreign-word entries."""

    # -- Lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Release any resources held by this store (no-op by default)."""
        return None

    # -- Convenience constructors -------------------------------------------

    @classmethod
    def load_default(cls) -> JsonLexiconStore:
        """Load all built-in JSON resources and return a store.

        This is a concrete convenience method so that consumers can write
        ``LexiconStore.load_default()`` without importing a specific backend.
        Returns a :class:`JsonLexiconStore`.
        """
        return JsonLexiconStore.load_default()


# ---------------------------------------------------------------------------
# JSON-backed implementation
# ---------------------------------------------------------------------------


class JsonLexiconStore(LexiconStore):
    """In-memory lexicon store loaded from built-in JSON resource files.

    This is the default backend.  Use :meth:`load_default` to load all
    built-in lexicon files at once, or construct an empty store and call
    the individual ``_load_*`` methods for partial loads.
    """

    def __init__(self) -> None:
        # no-tone key → LexiconEntry (syllables)
        self._syllable_index: dict[str, list[LexiconEntry]] = {}
        # surface form → LexiconEntry (syllables)
        self._syllable_by_surface: dict[str, list[LexiconEntry]] = {}
        # no-tone key → LexiconEntry (words + units)
        self._word_index: dict[str, list[LexiconEntry]] = {}
        # surface form → LexiconEntry (words + units)
        self._word_by_surface: dict[str, list[LexiconEntry]] = {}
        # abbreviation → AbbreviationEntry
        self._abbrev_entries: dict[str, AbbreviationEntry] = {}
        # no-tone key → PhraseEntry
        self._phrase_index: dict[str, list[PhraseEntry]] = {}
        # exact phrase surface → PhraseEntry
        self._phrase_surfaces: dict[str, list[PhraseEntry]] = {}
        # noisy token → list of correction surfaces
        self._ocr_confusions: dict[str, list[str]] = {}
        # noisy token → OcrConfusionEntry
        self._ocr_confusion_entries: dict[str, OcrConfusionEntry] = {}
        # foreign terms set
        self._foreign_words: set[str] = set()
        # All word/unit surface forms for quick contains check
        self._word_surfaces: set[str] = set()

    # -- Loading -----------------------------------------------------------

    @classmethod
    def load_default(cls) -> JsonLexiconStore:
        """Load all built-in JSON lexicon files and return a new store."""
        store = cls()
        store._load_syllables()
        store._load_words()
        store._load_units()
        store._load_abbreviations()
        store._load_foreign_words()
        store._load_phrases()
        store._load_ocr_confusions()
        return store

    def _load_syllables(self) -> None:
        data: list[dict[str, object]] = load_json_resource("syllables.vi.json")  # type: ignore[assignment]
        for entry in data:
            base = str(entry["base"])
            raw_forms = entry["forms"]
            forms: list[str] = [str(f) for f in raw_forms] if isinstance(raw_forms, list) else []
            freq_map: dict[str, float] = {}
            raw_freq = entry.get("freq")
            if isinstance(raw_freq, dict):
                freq_map = {str(k): float(v) for k, v in raw_freq.items()}

            for form in forms:
                conf = freq_map.get(form, 0.5)
                lex_entry = LexiconEntry(
                    entry_id=f"syllable/{form}",
                    surface=form,
                    normalized=form,
                    no_tone=base,
                    kind=LexiconKind.SYLLABLE,
                    score=Score(confidence=conf, frequency=conf),
                    provenance=Provenance(source=LexiconSource.BUILT_IN),
                    tags=("syllable",),
                )
                if base not in self._syllable_index:
                    self._syllable_index[base] = []
                self._syllable_index[base].append(lex_entry)

                if form not in self._syllable_by_surface:
                    self._syllable_by_surface[form] = []
                self._syllable_by_surface[form].append(lex_entry)

    def _load_words(self) -> None:
        data: list[dict[str, object]] = load_json_resource("words.vi.json")  # type: ignore[assignment]
        for entry in data:
            surface = str(entry["surface"])
            freq = float(entry.get("freq", 1.0))  # type: ignore[arg-type]
            entry_type = str(entry.get("type", "word"))
            raw_domain = entry.get("domain")
            domain = str(raw_domain) if raw_domain is not None else None
            inferred_kind = self._infer_kind(entry_type)
            no_tone = strip_accents(surface)
            lex_entry = LexiconEntry(
                entry_id=f"word/{surface}",
                surface=surface,
                normalized=surface,
                no_tone=no_tone,
                kind=inferred_kind,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
                domain=domain,
                tags=(entry_type,),
            )
            if surface not in self._word_by_surface:
                self._word_by_surface[surface] = []
            self._word_by_surface[surface].append(lex_entry)
            self._word_surfaces.add(surface)
            if no_tone not in self._word_index:
                self._word_index[no_tone] = []
            self._word_index[no_tone].append(lex_entry)

    def _load_units(self) -> None:
        data: list[dict[str, object]] = load_json_resource("units.vi.json")  # type: ignore[assignment]
        for entry in data:
            surface = str(entry["surface"])
            freq = float(entry.get("freq", 1.0))  # type: ignore[arg-type]
            raw_domain = entry.get("domain", "measurement")
            domain = str(raw_domain) if raw_domain is not None else "measurement"
            no_tone = strip_accents(surface)
            lex_entry = LexiconEntry(
                entry_id=f"unit/{surface}",
                surface=surface,
                normalized=surface,
                no_tone=no_tone,
                kind=LexiconKind.UNIT,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
                domain=domain,
                tags=("unit",),
            )
            if surface not in self._word_by_surface:
                self._word_by_surface[surface] = []
            self._word_by_surface[surface].append(lex_entry)
            self._word_surfaces.add(surface)
            if no_tone not in self._word_index:
                self._word_index[no_tone] = []
            self._word_index[no_tone].append(lex_entry)

    def _load_abbreviations(self) -> None:
        data: list[dict[str, object]] = load_json_resource("abbreviations.vi.json")  # type: ignore[assignment]
        for entry in data:
            abbrev = str(entry["abbreviation"])
            raw_exps = entry["expansions"]
            expansions = tuple(str(e) for e in raw_exps) if isinstance(raw_exps, list) else ()
            normalized = str(entry.get("normalized", abbrev.lower()))
            raw_tags = entry.get("tags")
            tags = tuple(raw_tags) if isinstance(raw_tags, list) else ()
            ambiguous = entry.get("ambiguous", len(expansions) > 1)
            if isinstance(ambiguous, bool):
                pass
            else:
                ambiguous = len(expansions) > 1
            self._abbrev_entries[abbrev] = AbbreviationEntry(
                entry_id=f"abbrev/{abbrev}",
                surface=abbrev,
                normalized=normalized,
                expansions=expansions,
                score=Score(confidence=1.0),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
                ambiguous=ambiguous,
                tags=tags,
            )

    def _load_foreign_words(self) -> None:
        raw_data = load_json_resource("foreign_words.json")
        if isinstance(raw_data, list):
            self._foreign_words = {str(item) for item in raw_data}

    def _load_phrases(self) -> None:
        data: list[dict[str, object]] = load_json_resource("phrases.vi.json")  # type: ignore[assignment]
        for entry in data:
            phrase = str(entry["phrase"])
            n_raw = entry["n"]
            n = int(n_raw) if isinstance(n_raw, (int, float)) else 0
            freq = float(entry.get("freq", 0.5))  # type: ignore[arg-type]
            raw_domain = entry.get("domain")
            domain = str(raw_domain) if raw_domain is not None else None
            raw_tags = entry.get("tags")
            tags = tuple(raw_tags) if isinstance(raw_tags, list) else ()
            no_tone = strip_accents(phrase)
            phrase_entry = PhraseEntry(
                entry_id=f"phrase/{phrase}",
                phrase=phrase,
                normalized=phrase,
                no_tone=no_tone,
                n=n,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
                domain=domain,
                tags=tags,
            )
            if no_tone not in self._phrase_index:
                self._phrase_index[no_tone] = []
            self._phrase_index[no_tone].append(phrase_entry)
            if phrase not in self._phrase_surfaces:
                self._phrase_surfaces[phrase] = []
            self._phrase_surfaces[phrase].append(phrase_entry)

    def _load_ocr_confusions(self) -> None:
        data: list[dict[str, object]] = load_json_resource("ocr_confusions.vi.json")  # type: ignore[assignment]
        for entry in data:
            noisy = str(entry["noisy"])
            raw_corrections = entry["corrections"]
            corrections: tuple[str, ...] = (
                tuple(str(c) for c in raw_corrections) if isinstance(raw_corrections, list) else ()
            )
            conf = float(entry.get("confidence", 0.7))  # type: ignore[arg-type]
            normalized_noisy = strip_accents(noisy)
            self._ocr_confusions[noisy] = list(corrections)
            self._ocr_confusion_entries[noisy] = OcrConfusionEntry(
                entry_id=f"ocr/{noisy}",
                noisy=noisy,
                normalized_noisy=normalized_noisy,
                corrections=corrections,
                score=Score(confidence=conf),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
            )

    @staticmethod
    def _infer_kind(entry_type: str) -> LexiconKind:
        kind_map: dict[str, LexiconKind] = {
            "common_word": LexiconKind.WORD,
            "unit_word": LexiconKind.UNIT,
        }
        return kind_map.get(entry_type, LexiconKind.WORD)

    # -- Surface / exact lookups -------------------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        entries: list[LexiconEntry | AbbreviationEntry | PhraseEntry] = []

        if text in self._syllable_by_surface:
            entries.extend(self._syllable_by_surface[text])

        if text in self._word_by_surface:
            entries.extend(self._word_by_surface[text])

        return LexiconLookupResult(
            query=text,
            found=bool(entries),
            entries=tuple(entries),
        )

    def lookup_syllable(self, text: str) -> list[str]:
        key = strip_accents(text)
        entries = self._syllable_index.get(key, [])
        return [e.surface for e in entries]

    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        entries = self._word_by_surface.get(text, [])
        return [e for e in entries if e.kind == LexiconKind.UNIT]

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        entry = self._abbrev_entries.get(text)
        return LexiconLookupResult(
            query=text,
            found=entry is not None,
            entries=(entry,) if entry is not None else (),
        )

    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        return list(self._phrase_surfaces.get(text, []))

    def lookup_phrase_str(self, text: str) -> str | None:
        key = strip_accents(text)
        entries = self._phrase_index.get(key, [])
        if entries:
            return entries[0].phrase
        return None

    # -- Accentless / no-tone lookups --------------------------------------

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        key = strip_accents(text)
        entries: list[LexiconEntry | AbbreviationEntry | PhraseEntry] = []

        if key in self._syllable_index:
            entries.extend(self._syllable_index[key])

        if key in self._word_index:
            entries.extend(self._word_index[key])

        return LexiconLookupResult(
            query=text,
            found=bool(entries),
            entries=tuple(entries),
        )

    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        return self.lookup_accentless(text)

    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        key = strip_accents(text)
        return list(self._phrase_index.get(key, []))

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        return list(self._syllable_index.get(no_tone_key, []))

    # -- OCR confusion -----------------------------------------------------

    def lookup_ocr(self, noisy: str) -> list[str]:
        return list(self._ocr_confusions.get(noisy, []))

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        corrections = self._ocr_confusions.get(noisy)
        if corrections:
            candidates = tuple(
                Candidate(text=c, score=0.7, source=CandidateSource.OCR_CONFUSION_INDEX)
                for c in corrections
            )
            return OcrConfusionLookupResult(query=noisy, found=True, corrections=candidates)
        return OcrConfusionLookupResult(query=noisy, found=False)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        return dict(self._ocr_confusions)

    # -- Membership --------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        return text in self._word_surfaces

    def contains_syllable(self, text: str) -> bool:
        return text in self._syllable_by_surface

    def contains_foreign_word(self, text: str) -> bool:
        return text in self._foreign_words

    # -- Aggregate / statistics --------------------------------------------

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        return list(self._abbrev_entries.values())

    def get_abbreviation_count(self) -> int:
        return len(self._abbrev_entries)

    def get_phrase_count(self) -> int:
        return len(self._phrase_index)

    def get_ocr_confusion_count(self) -> int:
        return len(self._ocr_confusions)

    def get_syllable_entry_count(self) -> int:
        return sum(len(v) for v in self._syllable_index.values())

    def get_word_count(self) -> int:
        return len(self._word_surfaces)

    def get_foreign_word_count(self) -> int:
        return len(self._foreign_words)


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def load_default_lexicon() -> JsonLexiconStore:
    """Load all built-in lexicon files and return a :class:`JsonLexiconStore`.

    Shorthand for ``JsonLexiconStore.load_default()``.
    """
    return JsonLexiconStore.load_default()
