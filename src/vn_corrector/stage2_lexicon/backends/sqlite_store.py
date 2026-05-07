"""SQLite-backed lexicon store.

Provides :class:`SqliteLexiconStore` — a production-ready backend that
uses the stdlib ``sqlite3`` module with no additional dependencies.

Includes the full populator that can build a database from the built-in
JSON resource files, and implements the ``is_protected_token`` bridge.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from vn_corrector.common.enums import CandidateIndexSource, LexiconKind, LexiconSource
from vn_corrector.common.lexicon import (
    AbbreviationEntry,
    LexiconCandidate,
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
)
from vn_corrector.common.scoring import Score
from vn_corrector.stage2_lexicon.core.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.core.normalize import normalize_key
from vn_corrector.stage2_lexicon.core.store import LexiconStore
from vn_corrector.stage2_lexicon.core.types import LexiconIndex

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lexicon_syllables (
    base    TEXT NOT NULL,
    surface TEXT NOT NULL,
    freq    REAL NOT NULL DEFAULT 0.5,
    PRIMARY KEY (base, surface)
);

CREATE TABLE IF NOT EXISTS lexicon_words (
    surface     TEXT NOT NULL PRIMARY KEY,
    normalized  TEXT NOT NULL DEFAULT '',
    no_tone     TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL DEFAULT 'word',
    type        TEXT NOT NULL DEFAULT 'word',
    source      TEXT,
    confidence  REAL NOT NULL DEFAULT 1.0,
    freq        REAL NOT NULL DEFAULT 1.0,
    domain      TEXT,
    tags        TEXT
);

CREATE INDEX IF NOT EXISTS idx_words_no_tone ON lexicon_words(no_tone);

CREATE TABLE IF NOT EXISTS lexicon_units (
    surface TEXT NOT NULL PRIMARY KEY,
    freq    REAL NOT NULL DEFAULT 1.0,
    domain  TEXT NOT NULL DEFAULT 'measurement'
);

CREATE TABLE IF NOT EXISTS lexicon_abbreviations (
    abbreviation TEXT NOT NULL PRIMARY KEY,
    normalized   TEXT NOT NULL,
    expansions   TEXT NOT NULL,
    ambiguous    INTEGER NOT NULL DEFAULT 0,
    tags         TEXT
);

CREATE TABLE IF NOT EXISTS lexicon_foreign_words (
    word TEXT NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS lexicon_phrases (
    phrase   TEXT NOT NULL PRIMARY KEY,
    normalized TEXT NOT NULL,
    no_tone  TEXT NOT NULL,
    n        INTEGER NOT NULL,
    freq     REAL NOT NULL DEFAULT 0.5,
    domain   TEXT,
    tags     TEXT
);

CREATE INDEX IF NOT EXISTS idx_phrases_no_tone ON lexicon_phrases(no_tone);

CREATE TABLE IF NOT EXISTS lexicon_ocr_confusions (
    noisy           TEXT NOT NULL PRIMARY KEY,
    normalized_noisy TEXT NOT NULL,
    corrections     TEXT NOT NULL,
    confidence      REAL NOT NULL DEFAULT 0.7
);

CREATE TABLE IF NOT EXISTS lexicon_build_metadata (
    key   TEXT NOT NULL PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class SqliteLexiconStore(LexiconStore):
    """Lexicon store backed by a read-only SQLite database.

    Args:
        db_path: Filesystem path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialise the store by opening a read-only SQLite database connection."""
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._lexicon_index: LexiconIndex | None = None

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    # -- Public constructors -----------------------------------------------

    @classmethod
    def from_db(cls, db_path: str | Path) -> SqliteLexiconStore:
        """Open an existing official runtime SQLite database at *db_path*.

        This is the canonical constructor for loading a pre-built
        ``trusted_lexicon.db`` produced by ``scripts/build_lexicon_db.py``.
        """
        return cls(db_path)

    @classmethod
    def from_path(cls, db_path: str | Path) -> SqliteLexiconStore:
        """Open an existing SQLite database at *db_path*."""
        return cls(db_path)

    # -- Core new methods ---------------------------------------------------

    def is_protected_token(self, text: str) -> bool:
        """Return ``True`` if *text* is a known foreign word or abbreviation."""
        normalized = normalize_key(text)
        if not normalized:
            return False

        # Check foreign words
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_foreign_words WHERE LOWER(word) = ? LIMIT 1",
            (normalized,),
        )
        if cur.fetchone() is not None:
            return True

        # Check abbreviations
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_abbreviations WHERE abbreviation = ? LIMIT 1",
            (text,),
        )
        if cur.fetchone() is not None:
            return True

        # Check domain-protected words
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_words WHERE surface = ? "
            "AND domain IN ('chemical', 'brand', 'code') LIMIT 1",
            (text,),
        )
        return cur.fetchone() is not None

    def get_lexicon_index(self) -> LexiconIndex:
        """Return the formal :class:`LexiconIndex` for this store.

        The index is built lazily from all SQLite tables on first access.
        """
        if self._lexicon_index is None:
            entries: list[LexiconEntry] = []

            # Syllables
            cur = self._conn.execute(
                "SELECT base, surface, freq FROM lexicon_syllables",
            )
            for row in cur.fetchall():
                entries.append(
                    _make_syllable_entry(
                        surface=row["surface"], no_tone=row["base"], freq=row["freq"]
                    )
                )

            # Words
            cur = self._conn.execute(
                "SELECT surface, type, freq, domain FROM lexicon_words",
            )
            for row in cur.fetchall():
                entries.append(_row_to_lexicon_entry("word", row["surface"], row))

            # Units
            cur = self._conn.execute(
                "SELECT surface, freq, domain FROM lexicon_units",
            )
            for row in cur.fetchall():
                entries.append(_row_to_unit_entry(row))

            self._lexicon_index = LexiconIndex.build(entries)

        return self._lexicon_index

    # -- Surface / exact lookups -------------------------------------------

    def lookup(self, text: str) -> LexiconLookupResult:
        """Look up *text* across syllables, words, and units."""
        rows: list[LexiconEntry | AbbreviationEntry | PhraseEntry] = []
        rows.extend(self._query_syllable_surface(text))
        rows.extend(self._query_word_surface(text))
        rows.extend(self._query_unit_surface(text))
        return LexiconLookupResult(query=text, found=bool(rows), entries=tuple(rows))

    def lookup_syllable(self, text: str) -> list[str]:
        """Return all surface forms for the accent-stripped base of *text*."""
        key = strip_accents(text)
        cur = self._conn.execute(
            "SELECT surface FROM lexicon_syllables WHERE base = ? ORDER BY surface",
            (key,),
        )
        return [row["surface"] for row in cur.fetchall()]

    def lookup_unit(self, text: str) -> list[LexiconEntry]:
        """Look up a measurement or unit word by exact surface."""
        cur = self._conn.execute(
            "SELECT surface, freq, domain FROM lexicon_units WHERE surface = ?",
            (text,),
        )
        return [_row_to_unit_entry(row) for row in cur.fetchall()]

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        """Look up an abbreviation by its exact form."""
        cur = self._conn.execute(
            "SELECT * FROM lexicon_abbreviations WHERE abbreviation = ?",
            (text,),
        )
        row = cur.fetchone()
        if row is None:
            return LexiconLookupResult(query=text, found=False)
        return LexiconLookupResult(
            query=text,
            found=True,
            entries=(_row_to_abbreviation_entry(row),),
        )

    def lookup_phrase(self, text: str) -> list[PhraseEntry]:
        """Look up a phrase by its exact surface form."""
        cur = self._conn.execute(
            "SELECT * FROM lexicon_phrases WHERE phrase = ?",
            (text,),
        )
        return [_row_to_phrase_entry(row) for row in cur.fetchall()]

    def lookup_phrase_str(self, text: str) -> str | None:
        """Return the first phrase matching the accent-stripped version of *text*."""
        key = strip_accents(text)
        cur = self._conn.execute(
            "SELECT phrase FROM lexicon_phrases WHERE no_tone = ? LIMIT 1",
            (key,),
        )
        row = cur.fetchone()
        return row["phrase"] if row is not None else None

    # -- Accentless / no-tone lookups --------------------------------------

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        """Look up *text* with accents stripped, matching syllables and words."""
        key = strip_accents(text)
        rows: list[LexiconEntry | AbbreviationEntry | PhraseEntry] = []
        rows.extend(self._query_syllable_base(key))
        rows.extend(self._query_word_no_tone(key))
        return LexiconLookupResult(query=text, found=bool(rows), entries=tuple(rows))

    def lookup_no_tone(self, text: str) -> LexiconLookupResult:
        """Alias for :meth:`lookup_accentless`."""
        return self.lookup_accentless(text)

    def lookup_phrase_normalized(self, text: str) -> list[PhraseEntry]:
        """Look up phrases whose no-tone key matches the accent-stripped *text*."""
        key = strip_accents(text)
        cur = self._conn.execute(
            "SELECT * FROM lexicon_phrases WHERE no_tone = ? ORDER BY phrase",
            (key,),
        )
        return [_row_to_phrase_entry(row) for row in cur.fetchall()]

    def get_syllable_candidates(self, no_tone_key: str) -> list[LexiconEntry]:
        """Return syllable entries for a given no-tone key, ordered by frequency descending."""
        cur = self._conn.execute(
            "SELECT surface, freq FROM lexicon_syllables WHERE base = ? ORDER BY freq DESC",
            (no_tone_key,),
        )
        return [
            _make_syllable_entry(surface=row["surface"], no_tone=no_tone_key, freq=row["freq"])
            for row in cur.fetchall()
        ]

    # -- OCR confusion -----------------------------------------------------

    def lookup_ocr(self, noisy: str) -> list[str]:
        """Return correction strings for a noisy OCR token."""
        cur = self._conn.execute(
            "SELECT corrections FROM lexicon_ocr_confusions WHERE noisy = ?",
            (noisy,),
        )
        row = cur.fetchone()
        if row is None:
            return []
        corrections: list[str] = json.loads(row["corrections"])
        return corrections

    def get_ocr_corrections(self, noisy: str) -> OcrConfusionLookupResult:
        """Look up OCR corrections for *noisy* with confidence scores."""
        cur = self._conn.execute(
            "SELECT corrections, confidence FROM lexicon_ocr_confusions WHERE noisy = ?",
            (noisy,),
        )
        row = cur.fetchone()
        if row is None:
            return OcrConfusionLookupResult(query=noisy, found=False)
        corrections: list[str] = json.loads(row["corrections"])
        score = row["confidence"]
        candidates = tuple(
            LexiconCandidate(text=c, score=score, source=CandidateIndexSource.OCR_CONFUSION_INDEX)
            for c in corrections
        )
        return OcrConfusionLookupResult(query=noisy, found=True, corrections=candidates)

    def get_all_ocr_confusions(self) -> dict[str, list[str]]:
        """Return every OCR confusion entry."""
        cur = self._conn.execute(
            "SELECT noisy, corrections FROM lexicon_ocr_confusions ORDER BY noisy",
        )
        result: dict[str, list[str]] = {}
        for row in cur.fetchall():
            result[row["noisy"]] = cast("list[str]", json.loads(row["corrections"]))
        return result

    # -- Membership --------------------------------------------------------

    def contains_word(self, text: str) -> bool:
        """Check whether *text* exists as a word or unit."""
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_words WHERE surface = ? "
            "UNION SELECT 1 FROM lexicon_units WHERE surface = ? LIMIT 1",
            (text, text),
        )
        return cur.fetchone() is not None

    def contains_syllable(self, text: str) -> bool:
        """Check whether *text* exists as a syllable."""
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_syllables WHERE surface = ? LIMIT 1",
            (text,),
        )
        return cur.fetchone() is not None

    def contains_foreign_word(self, text: str) -> bool:
        """Check whether *text* exists as a foreign word."""
        cur = self._conn.execute(
            "SELECT 1 FROM lexicon_foreign_words WHERE word = ? LIMIT 1",
            (text,),
        )
        return cur.fetchone() is not None

    # -- Aggregate / statistics --------------------------------------------

    def get_abbreviation_entries(self) -> list[AbbreviationEntry]:
        """Return all abbreviation entries, ordered alphabetically."""
        cur = self._conn.execute("SELECT * FROM lexicon_abbreviations ORDER BY abbreviation")
        return [_row_to_abbreviation_entry(row) for row in cur.fetchall()]

    def get_abbreviation_count(self) -> int:
        """Return the total number of abbreviation entries."""
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM lexicon_abbreviations")
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    def get_phrase_count(self) -> int:
        """Return the number of distinct normalized phrases."""
        cur = self._conn.execute(
            "SELECT COUNT(DISTINCT no_tone) AS cnt FROM lexicon_phrases",
        )
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    def get_ocr_confusion_count(self) -> int:
        """Return the total number of OCR confusion entries."""
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM lexicon_ocr_confusions")
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    def get_syllable_entry_count(self) -> int:
        """Return the total number of syllable entries."""
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM lexicon_syllables")
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    def get_word_count(self) -> int:
        """Return the combined count of words and units."""
        cur = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM ("
            "SELECT surface FROM lexicon_words "
            "UNION SELECT surface FROM lexicon_units"
            ")",
        )
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    def get_foreign_word_count(self) -> int:
        """Return the total number of foreign word entries."""
        cur = self._conn.execute("SELECT COUNT(*) AS cnt FROM lexicon_foreign_words")
        row = cur.fetchone()
        return row["cnt"] if row is not None else 0

    # -- Internal query helpers --------------------------------------------

    def _query_syllable_surface(self, text: str) -> list[LexiconEntry]:
        cur = self._conn.execute(
            "SELECT base, surface, freq FROM lexicon_syllables WHERE surface = ?",
            (text,),
        )
        return [
            _make_syllable_entry(surface=row["surface"], no_tone=row["base"], freq=row["freq"])
            for row in cur.fetchall()
        ]

    def _query_syllable_base(self, key: str) -> list[LexiconEntry]:
        cur = self._conn.execute(
            "SELECT surface, freq FROM lexicon_syllables WHERE base = ?",
            (key,),
        )
        return [
            _make_syllable_entry(surface=row["surface"], no_tone=key, freq=row["freq"])
            for row in cur.fetchall()
        ]

    def _query_word_surface(self, text: str) -> list[LexiconEntry]:
        cur = self._conn.execute(
            "SELECT surface, type, freq, domain, normalized, "
            "no_tone, kind, source, confidence, tags "
            "FROM lexicon_words WHERE surface = ?",
            (text,),
        )
        return [_row_to_lexicon_entry("word", text, row) for row in cur.fetchall()]

    def _query_unit_surface(self, text: str) -> list[LexiconEntry]:
        cur = self._conn.execute(
            "SELECT surface, freq, domain FROM lexicon_units WHERE surface = ?",
            (text,),
        )
        return [_row_to_unit_entry(row) for row in cur.fetchall()]

    def _query_word_no_tone(self, key: str) -> list[LexiconEntry]:
        cur = self._conn.execute(
            "SELECT surface, type, freq, domain, normalized, "
            "no_tone, kind, source, confidence, tags "
            "FROM lexicon_words WHERE no_tone = ?",
            (key,),
        )
        return [_row_to_lexicon_entry("word", row["surface"], row) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Row → dataclass helpers  (same as original backends.py)
# ---------------------------------------------------------------------------


def _make_syllable_entry(*, surface: str, no_tone: str, freq: float) -> LexiconEntry:
    return LexiconEntry(
        entry_id=f"syllable/{surface}",
        surface=surface,
        normalized=surface,
        no_tone=no_tone,
        kind=LexiconKind.SYLLABLE,
        score=Score(confidence=freq, frequency=freq),
        provenance=Provenance(source=LexiconSource.BUILT_IN),
        tags=("syllable",),
    )


def _row_to_lexicon_entry(
    prefix: str,
    surface: str,
    row: sqlite3.Row,
) -> LexiconEntry:
    r = dict(row)
    kind = _infer_kind(str(r["type"])) if "type" in r else LexiconKind.WORD
    freq = float(r.get("freq", 1.0))
    domain: str | None = r.get("domain")
    no_tone: str = r.get("no_tone") or strip_accents(surface)
    normalized: str = r.get("normalized", surface)
    confidence = float(r.get("confidence", freq))
    try:
        source = LexiconSource(r["source"]) if r.get("source") else LexiconSource.BUILT_IN
    except ValueError:
        source = LexiconSource.BUILT_IN
    raw_tags = r.get("tags")
    tags: tuple[str, ...] = tuple(json.loads(raw_tags)) if raw_tags else ("word",)
    raw_kind = r.get("kind")
    entry_kind = LexiconKind(raw_kind) if raw_kind else kind
    return LexiconEntry(
        entry_id=f"{prefix}/{surface}",
        surface=surface,
        normalized=normalized,
        no_tone=no_tone,
        kind=entry_kind,
        score=Score(confidence=confidence, frequency=freq),
        provenance=Provenance(source=source),
        domain=domain,
        tags=tags,
    )


def _row_to_abbreviation_entry(row: sqlite3.Row) -> AbbreviationEntry:
    expansions: list[str] | tuple[str, ...] = json.loads(row["expansions"])
    tags_raw = row["tags"]
    tags: tuple[str, ...] = tuple(json.loads(tags_raw)) if tags_raw else ()
    return AbbreviationEntry(
        entry_id=f"abbrev/{row['abbreviation']}",
        surface=row["abbreviation"],
        normalized=row["normalized"],
        expansions=tuple(expansions),
        score=Score(confidence=1.0),
        provenance=Provenance(source=LexiconSource.BUILT_IN),
        ambiguous=bool(row["ambiguous"]),
        tags=tags,
    )


def _row_to_phrase_entry(row: sqlite3.Row) -> PhraseEntry:
    tags_raw = row["tags"]
    tags: tuple[str, ...] = tuple(json.loads(tags_raw)) if tags_raw else ()
    return PhraseEntry(
        entry_id=f"phrase/{row['phrase']}",
        phrase=row["phrase"],
        normalized=row["normalized"],
        no_tone=row["no_tone"],
        n=row["n"],
        score=Score(confidence=row["freq"], frequency=row["freq"]),
        provenance=Provenance(source=LexiconSource.BUILT_IN),
        domain=row["domain"],
        tags=tags,
    )


def _row_to_unit_entry(row: sqlite3.Row) -> LexiconEntry:
    return LexiconEntry(
        entry_id=f"unit/{row['surface']}",
        surface=row["surface"],
        normalized=row["surface"],
        no_tone=strip_accents(row["surface"]),
        kind=LexiconKind.UNIT,
        score=Score(confidence=row["freq"], frequency=row["freq"]),
        provenance=Provenance(source=LexiconSource.BUILT_IN),
        domain=row["domain"],
        tags=("unit",),
    )


def _infer_kind(entry_type: str) -> LexiconKind:
    kind_map: dict[str, LexiconKind] = {
        "common_word": LexiconKind.WORD,
        "unit_word": LexiconKind.UNIT,
    }
    return kind_map.get(entry_type, LexiconKind.WORD)
