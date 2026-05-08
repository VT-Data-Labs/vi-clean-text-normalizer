"""Stage-2 lexicon backends.

Provides :class:`LexiconDataStore` — the in-memory production backend
loadable from JSON and/or SQLite sources.

:data:`_SCHEMA_SQL` is the DDL for building test databases.
"""

from vn_corrector.stage2_lexicon.backends.data_store import LexiconDataStore

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lexicon_syllables (
    base         TEXT NOT NULL,
    surface      TEXT NOT NULL,
    freq         REAL NOT NULL DEFAULT 0.5,
    freq_count   REAL NOT NULL DEFAULT 0.0,
    freq_no_tone REAL NOT NULL DEFAULT 0.0,
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

__all__ = [
    "_SCHEMA_SQL",
    "LexiconDataStore",
]
