"""Lexicon store for Vietnamese correction pipeline.

Provides in-memory storage and lookup for syllables, words, units,
abbreviations, phrases, OCR confusions, and foreign terms loaded
from built-in JSON resources.
"""

from __future__ import annotations

import json
from importlib.resources import files as resource_files
from pathlib import Path

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

    Stores syllables indexed by no-tone key, words and units by surface
    form, abbreviations with multiple expansions, phrases by no-tone key,
    OCR confusions by noisy token, and foreign terms for quick membership.
    """

    def __init__(self) -> None:
        # no-tone key -> LexiconEntry (syllables)
        self._syllable_index: dict[str, list[LexiconEntry]] = {}
        # surface form -> LexiconEntry (syllables)
        self._syllable_by_surface: dict[str, list[LexiconEntry]] = {}
        # no-tone key -> LexiconEntry (words + units)
        self._word_index: dict[str, list[LexiconEntry]] = {}
        # surface form -> LexiconEntry (words + units)
        self._word_by_surface: dict[str, list[LexiconEntry]] = {}
        # abbreviation -> AbbreviationEntry
        self._abbrev_entries: dict[str, AbbreviationEntry] = {}
        # no-tone key -> PhraseEntry
        self._phrase_index: dict[str, list[PhraseEntry]] = {}
        # exact phrase surface -> PhraseEntry
        self._phrase_surfaces: dict[str, list[PhraseEntry]] = {}
        # noisy token -> list of correction surfaces
        self._ocr_confusions: dict[str, list[str]] = {}
        # noisy token -> OcrConfusionEntry
        self._ocr_confusion_entries: dict[str, OcrConfusionEntry] = {}
        # foreign terms set
        self._foreign_words: set[str] = set()
        # All word/unit surface forms for quick contains check
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
        store._load_phrases()
        store._load_ocr_confusions()
        return store

    @classmethod
    def load(cls) -> LexiconStore:
        """Alias for load_default()."""
        return cls.load_default()

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
        data: list[dict[str, object]] = _load_json("words.vi.json")  # type: ignore[assignment]
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
        data: list[dict[str, object]] = _load_json("units.vi.json")  # type: ignore[assignment]
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
        data: list[dict[str, object]] = _load_json("abbreviations.vi.json")  # type: ignore[assignment]
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
        raw_data = _load_json("foreign_words.json")
        if isinstance(raw_data, list):
            self._foreign_words = {str(item) for item in raw_data}

    def _load_phrases(self) -> None:
        data: list[dict[str, object]] = _load_json("phrases.vi.json")  # type: ignore[assignment]
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
        data: list[dict[str, object]] = _load_json("ocr_confusions.vi.json")  # type: ignore[assignment]
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

    # ------------------------------------------------------------------
    # Lookup — high-level string-returning API
    # ------------------------------------------------------------------

    def lookup_syllable(self, text: str) -> list[str]:
        """Return syllable candidate surfaces for any Vietnamese text.

        Strips accents and lowercases the input, then returns matching
        syllable surface forms.  Uppercase, accented, or mixed input all
        produce the same result.
        """
        key = strip_accents(text)
        entries = self._syllable_index.get(key, [])
        return [e.surface for e in entries]

    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        """Return unit entries by surface form."""
        entries = self._word_by_surface.get(text, [])
        return [e for e in entries if e.kind == LexiconKind.UNIT]

    def lookup_phrase_str(self, text: str) -> str | None:
        """Look up a phrase by its no-tone (accentless) form.

        Returns the accented surface form of the first match, or None.
        """
        key = strip_accents(text)
        entries = self._phrase_index.get(key, [])
        if entries:
            return entries[0].phrase
        return None

    def lookup_ocr(self, noisy: str) -> list[str]:
        """Return known OCR confusion corrections for a noisy token."""
        return list(self._ocr_confusions.get(noisy, []))

    # ------------------------------------------------------------------
    # Lookup — detailed typed API
    # ------------------------------------------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up text by exact surface form across syllables and words."""
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

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up by accentless normalized form (syllables and words)."""
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

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up an abbreviation and return its expansions."""
        entry = self._abbrev_entries.get(text)
        return LexiconLookupResult(
            query=text,
            found=entry is not None,
            entries=(entry,) if entry is not None else (),
        )

    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        """Look up by no-tone key (alias for lookup_accentless)."""
        return self.lookup_accentless(text)

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return all syllable entries matching a no-tone key.

        Args:
            no_tone_key: The accentless lookup key (e.g. ``"muong"``).

        Returns:
            List of matching syllable LexiconEntry objects, or empty list.
        """
        return list(self._syllable_index.get(no_tone_key, []))

    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by exact surface form."""
        return list(self._phrase_surfaces.get(text, []))

    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by no-tone (accentless) form."""
        key = strip_accents(text)
        return list(self._phrase_index.get(key, []))

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        """Get known corrections for a noisy OCR token.

        Returns:
            OcrConfusionLookupResult with Candidate objects.
        """
        corrections = self._ocr_confusions.get(noisy)
        if corrections:
            candidates = tuple(
                Candidate(text=c, score=0.7, source=CandidateSource.OCR_CONFUSION_INDEX)
                for c in corrections
            )
            return OcrConfusionLookupResult(query=noisy, found=True, corrections=candidates)
        return OcrConfusionLookupResult(query=noisy, found=False)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        """Return the full OCR confusion map (noisy -> correction surfaces)."""
        return dict(self._ocr_confusions)

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        """Check if text is a known word or unit (surface form match)."""
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
        return len(self._abbrev_entries)

    def get_phrase_count(self) -> int:
        """Return the number of unique phrase no-tone keys."""
        return len(self._phrase_index)

    def get_ocr_confusion_count(self) -> int:
        """Return the number of OCR confusion entries."""
        return len(self._ocr_confusions)
