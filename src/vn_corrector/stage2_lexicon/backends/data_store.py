"""In-memory lexicon data store — the single production backend.

:class:`LexiconDataStore` loads all lexicon entries from JSON resource
files and/or a SQLite database into memory at initialisation time.
After loading, **every lookup hits memory only** — SQLite is never
queried at runtime.
"""

from __future__ import annotations

import json as _json
import sqlite3
from pathlib import Path
from typing import cast

from vn_corrector.common.enums import CandidateIndexSource, LexiconKind, LexiconSource
from vn_corrector.common.lexicon import (
    AbbreviationEntry,
    LexiconCandidate,
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionEntry,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
)
from vn_corrector.common.scoring import Score
from vn_corrector.stage2_lexicon.core.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.core.normalize import normalize_key
from vn_corrector.stage2_lexicon.core.store import LexiconStore
from vn_corrector.stage2_lexicon.core.types import LexiconIndex

_RESOURCE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "resources" / "lexicons"
)

_DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "data"
    / "lexicon"
    / "trusted_lexicon.db"
)


def resource_path(filename: str) -> Path:
    """Return the filesystem path to a built-in lexicon resource file."""
    return _RESOURCE_DIR / filename


def load_json_resource(filename: str) -> list[dict[str, object]]:
    """Load and parse a JSON resource file from the built-in resources."""
    path = resource_path(filename)
    with path.open(encoding="utf-8") as f:
        return cast("list[dict[str, object]]", _json.load(f))


class LexiconDataStore(LexiconStore):
    """In-memory lexicon store loadable from JSON and/or SQLite sources.

    All lexicon data is loaded into memory at initialisation time.
    Runtime correction does **not** read SQLite.

    Usage::

        store = LexiconDataStore.from_json()
        store = LexiconDataStore.from_sqlite(Path("trusted_lexicon.db"))
        store = LexiconDataStore.from_json_and_sqlite()
    """

    def __init__(self) -> None:
        # -- Raw data ----------------------------------------------------------
        self._syllable_data: list[LexiconEntry] = []
        self._word_data: list[LexiconEntry] = []
        self._unit_data: list[LexiconEntry] = []
        self._abbrev_data: dict[str, AbbreviationEntry] = {}
        self._phrase_data: list[PhraseEntry] = []
        self._phrase_surfaces: dict[str, list[PhraseEntry]] = {}
        self._ocr_data: dict[str, list[str]] = {}
        self._ocr_entry_data: dict[str, OcrConfusionEntry] = {}
        self._foreign_words: set[str] = set()
        self._word_surfaces: set[str] = set()

        # -- Derived index -----------------------------------------------------
        self._syllable_index: dict[str, list[LexiconEntry]] = {}
        self._syllable_by_surface: dict[str, list[LexiconEntry]] = {}
        self._word_index: dict[str, list[LexiconEntry]] = {}
        self._word_by_surface: dict[str, list[LexiconEntry]] = {}
        self._phrase_index: dict[str, list[PhraseEntry]] = {}
        self._ocr_confusion_entries: dict[str, OcrConfusionEntry] = {}

        # -- Formal LexiconIndex (derived on demand) ---------------------------
        self._lexicon_index: LexiconIndex | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def data(self) -> list[LexiconEntry]:
        """All raw lexicon entries (flat list)."""
        return list(self._syllable_data + self._word_data + self._unit_data)

    @property
    def index(self) -> LexiconIndex:
        """The formal :class:`LexiconIndex` (built on first access)."""
        if self._lexicon_index is None:
            self._lexicon_index = LexiconIndex.build(self.data)
        return self._lexicon_index

    # ------------------------------------------------------------------
    # Loaders — JSON
    # ------------------------------------------------------------------

    def load_json_resources(self, _resources_dir: Path | None = None) -> None:
        """Load all built-in JSON lexicon resource files into this store.

        Currently uses the default resource directory
        (``resources/lexicons/``).  The *resources_dir* parameter is
        reserved for future use.
        """
        self._load_syllables()
        self._load_words()
        self._load_units()
        self._load_abbreviations()
        self._load_foreign_words()
        self._load_phrases()
        self._load_ocr_confusions()

    @classmethod
    def from_json(cls, resources_dir: Path | None = None) -> LexiconDataStore:
        """Build a store from JSON resource files only."""
        store = cls()
        store.load_json_resources(resources_dir)
        return store

    # ------------------------------------------------------------------
    # Loaders — SQLite (absorb into memory, then close)
    # ------------------------------------------------------------------

    def load_sqlite(self, db_path: Path) -> None:
        """Read all lexicon tables from *db_path* into memory, then close the DB.

        All lexicon data is loaded at init time.  Subsequent lookups do
        **not** read SQLite.
        """
        conn = sqlite3.connect(str(db_path))

        seen_ids: set[str] = set()
        for e in self._syllable_data:
            seen_ids.add(e.entry_id)
        for e in self._word_data:
            seen_ids.add(e.entry_id)
        for e in self._unit_data:
            seen_ids.add(e.entry_id)

        # -- Syllables ---------------------------------------------------------
        for row in conn.execute(
            "SELECT base, surface, freq FROM lexicon_syllables ORDER BY base, surface"
        ):
            base, surface, freq = row
            eid = f"syllable/{surface}"
            if eid in seen_ids:
                continue
            entry = LexiconEntry(
                entry_id=eid,
                surface=surface,
                normalized=surface,
                no_tone=base,
                kind=LexiconKind.SYLLABLE,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
                tags=("syllable", "trusted"),
            )
            self._syllable_data.append(entry)
            self._syllable_index.setdefault(base, []).append(entry)
            self._syllable_by_surface.setdefault(surface, []).append(entry)
            seen_ids.add(eid)

        # -- Words -------------------------------------------------------------
        for row in conn.execute(
            "SELECT surface, type, freq, domain, normalized, no_tone, "
            "kind, source, confidence, tags FROM lexicon_words"
        ):
            surface = row[0]
            eid = f"word/{surface}"
            if eid in seen_ids:
                continue
            entry_type = row[1] or "word"
            freq = float(row[2] or 1.0)
            domain = row[3]
            normalized = row[4] or surface
            no_tone = row[5] or strip_accents(surface)
            kind_str = row[6] or entry_type
            src_str = row[7] or "external-dictionary"
            conf = float(row[8] or freq)
            raw_tags = row[9]
            tags = tuple(_json.loads(raw_tags)) if raw_tags else ("word", "trusted")
            lex_kind = LexiconKind(kind_str) if kind_str else LexiconKind.WORD
            src = LexiconSource(src_str) if src_str else LexiconSource.EXTERNAL_DICTIONARY
            entry = LexiconEntry(
                entry_id=eid,
                surface=surface,
                normalized=normalized,
                no_tone=no_tone,
                kind=lex_kind,
                score=Score(confidence=conf, frequency=freq),
                provenance=Provenance(source=src),
                domain=domain,
                tags=tags,
            )
            self._word_data.append(entry)
            self._word_index.setdefault(no_tone, []).append(entry)
            self._word_by_surface.setdefault(surface, []).append(entry)
            self._word_surfaces.add(surface)
            seen_ids.add(eid)

        # -- Units (stored in same words table with kind='unit') ---------------
        for row in conn.execute(
            "SELECT surface, type, freq, domain, normalized, no_tone, "
            "kind, source, confidence, tags FROM lexicon_words WHERE kind = 'unit'"
        ):
            surface = row[0]
            eid = f"unit/{surface}"
            if eid in seen_ids:
                continue
            freq = float(row[2] or 1.0)
            domain = row[3] or "measurement"
            normalized = row[4] or surface
            no_tone = row[5] or strip_accents(surface)
            conf = float(row[8] or freq)
            raw_tags = row[9]
            tags = tuple(_json.loads(raw_tags)) if raw_tags else ("unit", "trusted")
            entry = LexiconEntry(
                entry_id=eid,
                surface=surface,
                normalized=normalized,
                no_tone=no_tone,
                kind=LexiconKind.UNIT,
                score=Score(confidence=conf, frequency=freq),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
                domain=domain,
                tags=tags,
            )
            self._unit_data.append(entry)
            self._word_index.setdefault(no_tone, []).append(entry)
            self._word_by_surface.setdefault(surface, []).append(entry)
            self._word_surfaces.add(surface)
            seen_ids.add(eid)

        # -- Abbreviations -----------------------------------------------------
        for row in conn.execute(
            "SELECT abbreviation, normalized, expansions, ambiguous, tags "
            "FROM lexicon_abbreviations"
        ):
            surface = row[0]
            eid = f"abbrev/{surface}"
            if eid in seen_ids:
                continue
            raw_expansions = row[2]
            expansions: tuple[str, ...] = (
                tuple(_json.loads(raw_expansions)) if raw_expansions else ()
            )
            ambiguous = bool(row[3]) if row[3] else len(expansions) > 1
            raw_tags = row[4]
            tags = tuple(_json.loads(raw_tags)) if raw_tags else ()
            self._abbrev_data[surface] = AbbreviationEntry(
                entry_id=eid,
                surface=surface,
                normalized=row[1] or surface.lower(),
                expansions=expansions,
                score=Score(confidence=1.0),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
                ambiguous=ambiguous,
                tags=tags,
            )
            seen_ids.add(eid)

        # -- Foreign words -----------------------------------------------------
        for row in conn.execute("SELECT word FROM lexicon_foreign_words"):
            self._foreign_words.add(row[0])

        # -- Units -------------------------------------------------------------
        for row in conn.execute("SELECT surface, freq, domain FROM lexicon_units"):
            surface = row[0]
            eid = f"unit/{surface}"
            if eid in seen_ids:
                continue
            freq = float(row[1] or 1.0)
            domain = row[2] or "measurement"
            no_tone = strip_accents(surface)
            entry = LexiconEntry(
                entry_id=eid,
                surface=surface,
                normalized=surface,
                no_tone=no_tone,
                kind=LexiconKind.UNIT,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
                domain=domain,
                tags=("unit", "trusted"),
            )
            self._unit_data.append(entry)
            self._word_index.setdefault(no_tone, []).append(entry)
            self._word_by_surface.setdefault(surface, []).append(entry)
            self._word_surfaces.add(surface)
            seen_ids.add(eid)

        # -- Phrases -----------------------------------------------------------
        for row in conn.execute("SELECT phrase, normalized, n, freq, domain FROM lexicon_phrases"):
            phrase = row[0]
            eid = f"phrase/{phrase}"
            if eid in seen_ids:
                continue
            normalized = row[1] or phrase
            n = int(row[2]) if row[2] else 2
            freq = float(row[3] or 0.5)
            domain = row[4]
            no_tone = strip_accents(phrase)
            phrase_entry = PhraseEntry(
                entry_id=eid,
                phrase=phrase,
                normalized=normalized,
                no_tone=no_tone,
                n=n,
                score=Score(confidence=freq, frequency=freq),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
                domain=domain,
            )
            self._phrase_data.append(phrase_entry)
            self._phrase_index.setdefault(no_tone, []).append(phrase_entry)
            self._phrase_surfaces.setdefault(phrase, []).append(phrase_entry)
            seen_ids.add(eid)

        # -- OCR confusions ----------------------------------------------------
        for row in conn.execute(
            "SELECT noisy, normalized_noisy, corrections, confidence FROM lexicon_ocr_confusions"
        ):
            noisy = row[0]
            eid = f"ocr/{noisy}"
            if eid in seen_ids:
                continue
            normalized_noisy = row[1] or strip_accents(noisy)
            raw_corrections = row[2]
            corrections: tuple[str, ...] = (
                tuple(_json.loads(raw_corrections)) if raw_corrections else ()
            )
            conf = float(row[3] or 0.7)
            normalized_noisy = strip_accents(noisy)
            self._ocr_data[noisy] = list(corrections)
            self._ocr_entry_data[noisy] = OcrConfusionEntry(
                entry_id=eid,
                noisy=noisy,
                normalized_noisy=normalized_noisy,
                corrections=corrections,
                score=Score(confidence=conf),
                provenance=Provenance(source=LexiconSource.EXTERNAL_DICTIONARY),
            )
            seen_ids.add(eid)

        conn.close()

    @classmethod
    def from_sqlite(cls, db_path: Path | None = None) -> LexiconDataStore:
        """Build a store from a SQLite lexicon database only."""
        store = cls()
        store.load_sqlite(db_path or _DEFAULT_DB_PATH)
        return store

    @classmethod
    def from_json_and_sqlite(
        cls,
        resources_dir: Path | None = None,
        db_path: Path | None = None,
    ) -> LexiconDataStore:
        """Build a store from JSON resources + SQLite, merged in-memory.

        JSON resources are loaded first; SQLite entries are merged in
        (skipping any ``entry_id`` already seen).  After this, all lookups
        hit memory only.
        """
        store = cls()
        store.load_json_resources(resources_dir)
        store.load_sqlite(db_path or _DEFAULT_DB_PATH)
        return store

    # ------------------------------------------------------------------
    # JSON load helpers
    # ------------------------------------------------------------------

    def _load_syllables(self) -> None:
        data: list[dict[str, object]] = load_json_resource("syllables.vi.json")
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
                self._syllable_data.append(lex_entry)
                self._syllable_index.setdefault(base, []).append(lex_entry)
                self._syllable_by_surface.setdefault(form, []).append(lex_entry)

    def _load_words(self) -> None:
        data: list[dict[str, object]] = load_json_resource("words.vi.json")
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
            self._word_data.append(lex_entry)
            self._word_by_surface.setdefault(surface, []).append(lex_entry)
            self._word_surfaces.add(surface)
            self._word_index.setdefault(no_tone, []).append(lex_entry)

    def _load_units(self) -> None:
        data: list[dict[str, object]] = load_json_resource("units.vi.json")
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
            self._unit_data.append(lex_entry)
            self._word_by_surface.setdefault(surface, []).append(lex_entry)
            self._word_surfaces.add(surface)
            self._word_index.setdefault(no_tone, []).append(lex_entry)

    def _load_abbreviations(self) -> None:
        data: list[dict[str, object]] = load_json_resource("abbreviations.vi.json")
        for entry in data:
            abbrev = str(entry["abbreviation"])
            raw_exps = entry["expansions"]
            expansions = tuple(str(e) for e in raw_exps) if isinstance(raw_exps, list) else ()
            normalized = str(entry.get("normalized", abbrev.lower()))
            raw_tags = entry.get("tags")
            tags = tuple(raw_tags) if isinstance(raw_tags, list) else ()
            ambiguous = entry.get("ambiguous", len(expansions) > 1)
            if not isinstance(ambiguous, bool):
                ambiguous = len(expansions) > 1
            self._abbrev_data[abbrev] = AbbreviationEntry(
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
        data: list[dict[str, object]] = load_json_resource("phrases.vi.json")
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
            self._phrase_data.append(phrase_entry)
            self._phrase_index.setdefault(no_tone, []).append(phrase_entry)
            self._phrase_surfaces.setdefault(phrase, []).append(phrase_entry)

    def _load_ocr_confusions(self) -> None:
        data: list[dict[str, object]] = load_json_resource("ocr_confusions.vi.json")
        for entry in data:
            noisy = str(entry["noisy"])
            raw_corrections = entry["corrections"]
            corrections: tuple[str, ...] = (
                tuple(str(c) for c in raw_corrections) if isinstance(raw_corrections, list) else ()
            )
            conf = float(entry.get("confidence", 0.7))  # type: ignore[arg-type]
            normalized_noisy = strip_accents(noisy)
            self._ocr_data[noisy] = list(corrections)
            self._ocr_entry_data[noisy] = OcrConfusionEntry(
                entry_id=f"ocr/{noisy}",
                noisy=noisy,
                normalized_noisy=normalized_noisy,
                corrections=corrections,
                score=Score(confidence=conf),
                provenance=Provenance(source=LexiconSource.BUILT_IN),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_kind(entry_type: str) -> LexiconKind:
        kind_map: dict[str, LexiconKind] = {
            "common_word": LexiconKind.WORD,
            "unit_word": LexiconKind.UNIT,
        }
        return kind_map.get(entry_type, LexiconKind.WORD)

    # ------------------------------------------------------------------
    # LexiconStore interface
    # ------------------------------------------------------------------

    def is_protected_token(self, text: str) -> bool:
        normalized = normalize_key(text)
        if not normalized:
            return False
        if normalized in {normalize_key(w) for w in self._foreign_words}:
            return True
        if text in self._abbrev_data:
            return True
        if text in self._word_surfaces:
            entry = self._word_by_surface.get(text, [None])[0]
            if entry is not None and entry.domain in ("chemical", "brand", "code"):
                return True
        return False

    def get_lexicon_index(self) -> LexiconIndex:
        return self.index

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
        entry = self._abbrev_data.get(text)
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

    def lookup_ocr(self, noisy: str) -> list[str]:
        return list(self._ocr_data.get(noisy, []))

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        corrections = self._ocr_data.get(noisy)
        if corrections:
            candidates = tuple(
                LexiconCandidate(
                    text=c,
                    score=0.7,
                    source=CandidateIndexSource.OCR_CONFUSION_INDEX,
                )
                for c in corrections
            )
            return OcrConfusionLookupResult(query=noisy, found=True, corrections=candidates)
        return OcrConfusionLookupResult(query=noisy, found=False)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        return dict(self._ocr_data)

    def contains_word(self, text: str) -> bool:
        return text in self._word_surfaces

    def contains_syllable(self, text: str) -> bool:
        return text in self._syllable_by_surface

    def contains_foreign_word(self, text: str) -> bool:
        return text in self._foreign_words

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        return list(self._abbrev_data.values())

    def get_abbreviation_count(self) -> int:
        return len(self._abbrev_data)

    def get_phrase_count(self) -> int:
        return len(self._phrase_index)

    def get_ocr_confusion_count(self) -> int:
        return len(self._ocr_data)

    def get_syllable_entry_count(self) -> int:
        return len(self._syllable_data)

    def get_word_count(self) -> int:
        return len(self._word_surfaces)

    def get_foreign_word_count(self) -> int:
        return len(self._foreign_words)


__all__ = [
    "LexiconDataStore",
]
