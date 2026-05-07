"""In-memory JSON-backed lexicon store.

Provides :class:`JsonLexiconStore` — the in-memory backend that loads only
human-curated JSON resource files.

This store does **not** load trusted-word data from JSONL or SQLite.
Use :class:`SqliteLexiconStore` or :class:`HybridLexiconStore` for
production pipelines that need the full trusted lexicon.
"""

from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resource_path(filename: str) -> Path:
    """Return the filesystem path to a built-in lexicon resource file."""
    return _RESOURCE_DIR / filename


def load_json_resource(filename: str) -> list[dict[str, object]] | dict[str, object]:
    """Load and parse a JSON resource file from the package's built-in resources."""
    path = resource_path(filename)
    with path.open(encoding="utf-8") as f:
        return cast("list[dict[str, object]] | dict[str, object]", json.load(f))


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class JsonLexiconStore(LexiconStore):
    """In-memory lexicon store loaded from built-in JSON resource files.

    Uses a formal :attr:`index` (:class:`LexiconIndex`) for O(1) lookups.
    The raw entry lists are kept in :attr:`data` for introspection and
    builder integration.

    This is backward-compatible with the original
    :class:`vn_corrector.common.lexicon.LexiconStoreInterface`.
    """

    def __init__(self) -> None:
        """Initialise an empty store with :attr:`data` and :attr:`index`."""
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

    # -- Properties -----------------------------------------------------------

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

    # -- Loading ---------------------------------------------------------------

    _default_store: JsonLexiconStore | None = None

    @classmethod
    def from_resources(cls) -> JsonLexiconStore:
        """Load all built-in JSON lexicon resource files.

        Loads only human-curated JSON resources:
        - syllables, words, units, abbreviations, foreign_words, phrases,
          ocr_confusions

        Does **not** load trusted-word JSONL or SQLite data.
        """
        if cls._default_store is not None:
            return cls._default_store
        store = cls()
        store._load_syllables()
        store._load_words()
        store._load_units()
        store._load_abbreviations()
        store._load_foreign_words()
        store._load_phrases()
        store._load_ocr_confusions()
        cls._default_store = store
        return store

    @classmethod
    def load_default(cls) -> JsonLexiconStore:
        """Deprecated alias for :meth:`from_resources`.

        .. deprecated::
            Use ``JsonLexiconStore.from_resources()`` or
            ``load_default_lexicon("json")`` instead.
        """
        return cls.from_resources()

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
                self._syllable_data.append(lex_entry)
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
            self._word_data.append(lex_entry)
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
            self._unit_data.append(lex_entry)
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
            self._phrase_data.append(phrase_entry)
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
            self._ocr_data[noisy] = list(corrections)
            self._ocr_entry_data[noisy] = OcrConfusionEntry(
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

    # -- Core new methods ---------------------------------------------------

    def is_protected_token(self, text: str) -> bool:
        """Return ``True`` if *text* is a known foreign word or abbreviation.

        This bridges M2 → M3 so that the protected-token matcher can query
        the lexicon for tokens that must never be modified.
        """
        normalized = normalize_key(text)
        if not normalized:
            return False
        # Check foreign words (case-insensitive in practice via normalize_key)
        if normalized in {normalize_key(w) for w in self._foreign_words}:
            return True
        # Check abbreviations
        if text in self._abbrev_data:
            return True
        # Check word surfaces
        if text in self._word_surfaces:
            entry = self._word_by_surface.get(text, [None])[0]
            if entry is not None and entry.domain in ("chemical", "brand", "code"):
                return True
        return False

    def get_lexicon_index(self) -> LexiconIndex:
        """Return the formal :class:`LexiconIndex` for this store."""
        return self.index

    # -- Surface / exact lookups (preserved) -------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up *text* by exact surface form across syllables and words."""
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
        """Return syllable surfaces matching the no-tone form of *text*."""
        key = strip_accents(text)
        entries = self._syllable_index.get(key, [])
        return [e.surface for e in entries]

    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        """Return unit entries whose surface exactly matches *text*."""
        entries = self._word_by_surface.get(text, [])
        return [e for e in entries if e.kind == LexiconKind.UNIT]

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up an abbreviation by its surface form."""
        entry = self._abbrev_data.get(text)
        return LexiconLookupResult(
            query=text,
            found=entry is not None,
            entries=(entry,) if entry is not None else (),
        )

    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by exact surface form."""
        return list(self._phrase_surfaces.get(text, []))

    def lookup_phrase_str(self, text: str) -> str | None:
        """Look up a phrase by its no-tone form, return the accented surface or ``None``."""
        key = strip_accents(text)
        entries = self._phrase_index.get(key, [])
        if entries:
            return entries[0].phrase
        return None

    # -- Accentless / no-tone lookups --------------------------------------

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up *text* by stripped/accentless form (syllables + words)."""
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
        """Alias for :meth:`lookup_accentless`."""
        return self.lookup_accentless(text)

    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        """Look up phrase entries by no-tone (accentless) form."""
        key = strip_accents(text)
        return list(self._phrase_index.get(key, []))

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return all syllable entries matching a no-tone key."""
        return list(self._syllable_index.get(no_tone_key, []))

    # -- OCR confusion -----------------------------------------------------

    def lookup_ocr(self, noisy: str) -> list[str]:
        """Return known correction surfaces for a noisy OCR token."""
        return list(self._ocr_data.get(noisy, []))

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        """Get known corrections for a noisy OCR token as structured result."""
        corrections = self._ocr_data.get(noisy)
        if corrections:
            candidates = tuple(
                LexiconCandidate(text=c, score=0.7, source=CandidateIndexSource.OCR_CONFUSION_INDEX)
                for c in corrections
            )
            return OcrConfusionLookupResult(query=noisy, found=True, corrections=candidates)
        return OcrConfusionLookupResult(query=noisy, found=False)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        """Return the full OCR confusion map (noisy -> correction surfaces)."""
        return dict(self._ocr_data)

    # -- Membership --------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        """Return ``True`` if *text* is a known word or unit (exact surface)."""
        return text in self._word_surfaces

    def contains_syllable(self, text: str) -> bool:
        """Return ``True`` if *text* is a known syllable (exact surface)."""
        return text in self._syllable_by_surface

    def contains_foreign_word(self, text: str) -> bool:
        """Return ``True`` if *text* is in the foreign-word list."""
        return text in self._foreign_words

    # -- Aggregate / statistics --------------------------------------------

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        """Return all abbreviation entries."""
        return list(self._abbrev_data.values())

    def get_abbreviation_count(self) -> int:
        """Return the number of abbreviation entries."""
        return len(self._abbrev_data)

    def get_phrase_count(self) -> int:
        """Return the number of unique phrase no-tone keys."""
        return len(self._phrase_index)

    def get_ocr_confusion_count(self) -> int:
        """Return the number of OCR confusion entries."""
        return len(self._ocr_data)

    def get_syllable_entry_count(self) -> int:
        """Return the total number of individual syllable entries."""
        return len(self._syllable_data)

    def get_word_count(self) -> int:
        """Return the number of known word/unit surface forms."""
        return len(self._word_surfaces)

    def get_foreign_word_count(self) -> int:
        """Return the number of foreign-word entries."""
        return len(self._foreign_words)
