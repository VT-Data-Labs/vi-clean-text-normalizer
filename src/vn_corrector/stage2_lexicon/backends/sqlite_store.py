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

from vn_corrector.common.types import (
    AbbreviationEntry,
    Candidate,
    CandidateSource,
    LexiconEntry,
    LexiconKind,
    LexiconLookupResult,
    LexiconSource,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
    Score,
)
from vn_corrector.lexicon.accent_stripper import strip_accents
from vn_corrector.stage2_lexicon.backends.json_store import load_json_resource
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
    surface TEXT NOT NULL PRIMARY KEY,
    type    TEXT NOT NULL DEFAULT 'word',
    freq    REAL NOT NULL DEFAULT 1.0,
    domain  TEXT
);

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
    def from_path(cls, db_path: str | Path) -> SqliteLexiconStore:
        """Open an existing SQLite database at *db_path*."""
        return cls(db_path)

    @classmethod
    def from_builtin_resources(
        cls,
        db_path: str | Path,
        *,
        overwrite: bool = False,
    ) -> SqliteLexiconStore:
        """Build a SQLite database from the built-in JSON resources and return a store."""
        path = Path(db_path)
        if not overwrite and path.exists():
            return cls(path)

        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.executescript(_SCHEMA_SQL)

        _populate_from_json(conn)
        conn.commit()
        conn.close()
        return cls(path)

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
            Candidate(text=c, score=score, source=CandidateSource.OCR_CONFUSION_INDEX)
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
            "SELECT surface, type, freq, domain FROM lexicon_words WHERE surface = ?",
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
            "SELECT surface, type, freq, domain FROM lexicon_words",
        )
        entries: list[LexiconEntry] = []
        for row in cur.fetchall():
            surface: str = row["surface"]
            if strip_accents(surface) == key:
                entries.append(
                    _row_to_lexicon_entry("word", surface, row),
                )
        return entries


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
    kind = _infer_kind(str(row["type"])) if "type" in row else LexiconKind.WORD
    freq = float(row["freq"]) if "freq" in row else 1.0
    domain: str | None = row["domain"] if "domain" in row else None  # noqa: SIM401 (sqlite3.Row has no .get())
    return LexiconEntry(
        entry_id=f"{prefix}/{surface}",
        surface=surface,
        normalized=surface,
        no_tone=strip_accents(surface),
        kind=kind,
        score=Score(confidence=freq, frequency=freq),
        provenance=Provenance(source=LexiconSource.BUILT_IN),
        domain=domain,
        tags=(str(row["type"]) if "type" in row else "word",),
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


# ---------------------------------------------------------------------------
# JSON → SQLite populator
# ---------------------------------------------------------------------------


def _populate_from_json(conn: sqlite3.Connection) -> None:
    """Populate a SQLite database from the built-in JSON resource files."""
    _populate_syllables(conn)
    _populate_words(conn)
    _populate_units(conn)
    _populate_abbreviations(conn)
    _populate_foreign_words(conn)
    _populate_phrases(conn)
    _populate_ocr_confusions(conn)


def _populate_syllables(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("syllables.vi.json")  # type: ignore[assignment]
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_syllables (base, surface, freq) VALUES (?, ?, ?)",
        _yield_syllable_rows(data),
    )


def _yield_syllable_rows(
    data: list[dict[str, object]],
) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for entry in data:
        base = str(entry["base"])
        raw_forms = entry["forms"]
        forms: list[str] = [str(f) for f in raw_forms] if isinstance(raw_forms, list) else []
        freq_map: dict[str, float] = {}
        raw_freq = entry.get("freq")
        if isinstance(raw_freq, dict):
            freq_map = {str(k): float(v) for k, v in raw_freq.items()}
        for form in forms:
            rows.append((base, form, freq_map.get(form, 0.5)))
    return rows


def _populate_words(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("words.vi.json")  # type: ignore[assignment]
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_words (surface, type, freq, domain) VALUES (?, ?, ?, ?)",
        [
            (
                str(entry["surface"]),
                str(entry.get("type", "word")),
                float(entry.get("freq", 1.0)),  # type: ignore[arg-type]
                entry.get("domain"),
            )
            for entry in data
        ],
    )


def _populate_units(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("units.vi.json")  # type: ignore[assignment]
    conn.executemany(
        "INSERT OR IGNORE INTO lexicon_units (surface, freq, domain) VALUES (?, ?, ?)",
        [
            (
                str(entry["surface"]),
                float(entry.get("freq", 1.0)),  # type: ignore[arg-type]
                str(entry.get("domain", "measurement")),
            )
            for entry in data
        ],
    )


def _populate_abbreviations(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("abbreviations.vi.json")  # type: ignore[assignment]
    sql = (
        "INSERT OR IGNORE INTO lexicon_abbreviations "
        "(abbreviation, normalized, expansions, ambiguous, tags) VALUES (?, ?, ?, ?, ?)"
    )
    rows: list[tuple[str, str, str, int, str]] = []
    for entry in data:
        expansions = entry.get("expansions")
        expansions_json = (
            json.dumps(expansions, ensure_ascii=False) if isinstance(expansions, list) else "[]"
        )
        ambiguous = entry.get("ambiguous", isinstance(expansions, list) and len(expansions) > 1)
        rows.append(
            (
                str(entry["abbreviation"]),
                str(entry.get("normalized", str(entry["abbreviation"]).lower())),
                expansions_json,
                _to_int(ambiguous),
                json.dumps(entry.get("tags", []), ensure_ascii=False),
            )
        )
    conn.executemany(sql, rows)


def _populate_foreign_words(conn: sqlite3.Connection) -> None:
    raw_data: list[dict[str, object]] | dict[str, object] = load_json_resource("foreign_words.json")
    if isinstance(raw_data, list):
        words = [str(item) for item in raw_data]
        conn.executemany(
            "INSERT OR IGNORE INTO lexicon_foreign_words (word) VALUES (?)",
            [(w,) for w in words],
        )


def _populate_phrases(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("phrases.vi.json")  # type: ignore[assignment]
    sql = (
        "INSERT OR IGNORE INTO lexicon_phrases "
        "(phrase, normalized, no_tone, n, freq, domain, tags) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    conn.executemany(
        sql,
        [
            (
                str(entry["phrase"]),
                str(entry.get("normalized", entry["phrase"])),
                strip_accents(str(entry["phrase"])),
                int(entry["n"]),  # type: ignore[call-overload]
                float(entry.get("freq", 0.5)),  # type: ignore[arg-type]
                entry.get("domain"),
                json.dumps(entry.get("tags", []), ensure_ascii=False),
            )
            for entry in data
        ],
    )


def _populate_ocr_confusions(conn: sqlite3.Connection) -> None:
    data: list[dict[str, object]] = load_json_resource("ocr_confusions.vi.json")  # type: ignore[assignment]
    sql = (
        "INSERT OR IGNORE INTO lexicon_ocr_confusions "
        "(noisy, normalized_noisy, corrections, confidence) VALUES (?, ?, ?, ?)"
    )
    conn.executemany(
        sql,
        [
            (
                str(entry["noisy"]),
                strip_accents(str(entry["noisy"])),
                json.dumps(entry["corrections"], ensure_ascii=False),
                float(entry.get("confidence", 0.7)),  # type: ignore[arg-type]
            )
            for entry in data
        ],
    )


def _to_int(value: object) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    return 1 if value else 0
