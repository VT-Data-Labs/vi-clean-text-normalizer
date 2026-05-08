"""Tests for LexiconStore — interface, loading, lookup, and membership.

Abstract test classes run against every backend; concrete subclasses
provide the store fixture for each backend variant.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

from scripts.build_trusted_lexicon_db import _populate_from_json
from vn_corrector.common.lexicon import (
    AbbreviationEntry,
)
from vn_corrector.stage2_lexicon import LexiconDataStore, LexiconStore, load_default_lexicon
from vn_corrector.stage2_lexicon.backends import _SCHEMA_SQL


def _build_test_db(db_path: str | Path) -> None:
    """Build a test SQLite DB from built-in JSON resources."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    _populate_from_json(conn, Path("resources/lexicons"))
    conn.commit()
    conn.close()


# ======================================================================
# Abstract test suite — runs against every backend
# ======================================================================


class _StoreTestBase:
    """Subclasses set :attr:`store` in their setUp."""

    store: LexiconStore

    # -- Loading -----------------------------------------------------------

    def test_load_default(self):
        assert isinstance(self.store, LexiconStore)

    def test_load_default_contains_syllables(self):
        assert self.store.contains_syllable("muỗng")

    def test_contains_known_syllable(self):
        assert self.store.contains_syllable("muỗng")

    def test_contains_known_word(self):
        assert self.store.contains_word("kg")

    def test_not_contains_unknown_syllable(self):
        assert not self.store.contains_syllable("zzzzzzz")

    def test_not_contains_unknown_word(self):
        assert not self.store.contains_word("zzzzzzz")

    def test_contains_known_syllable_accentless(self):
        assert self.store.contains_syllable("muỗng")

    # -- Lookup (exact) ----------------------------------------------------

    def test_lookup_known_syllable(self):
        result = self.store.lookup("muỗng")
        assert result.found
        assert len(result.entries) > 0

    def test_lookup_unknown(self):
        result = self.store.lookup("zzzzzzz")
        assert not result.found

    def test_lookup_known_word(self):
        result = self.store.lookup("hướng")
        assert result.found

    def test_lookup_abbreviation(self):
        result = self.store.lookup_abbreviation("2pn")
        assert result.found
        assert len(result.entries) > 0

    def test_lookup_abbreviation_unknown(self):
        result = self.store.lookup_abbreviation("zzz")
        assert not result.found

    def test_lookup_syllable(self):
        candidates = self.store.lookup_syllable("muong")
        assert len(candidates) > 0
        assert "muỗng" in candidates

    def test_lookup_unit_known(self):
        units = self.store.lookup_unit("kg")
        assert len(units) > 0
        assert all(e.kind.name == "UNIT" for e in units)

    def test_lookup_unit_unknown(self):
        units = self.store.lookup_unit("zzzzzzz")
        assert len(units) == 0

    # -- Lookup (accentless) -----------------------------------------------

    def test_accentless_known(self):
        result = self.store.lookup_accentless("huong")
        assert result.found

    def test_accentless_strips_accents(self):
        result = self.store.lookup_accentless("hướng")
        assert result.found

    def test_accentless_unknown(self):
        result = self.store.lookup_accentless("zzzzzzz")
        assert not result.found

    def test_no_tone_alias(self):
        result = self.store.lookup_no_tone("huong")
        assert result.found

    # -- Phrase lookups ----------------------------------------------------

    def test_lookup_phrase(self):
        result = self.store.lookup_phrase("số muỗng gạt ngang")
        assert len(result) > 0
        assert result[0].phrase == "số muỗng gạt ngang"

    def test_lookup_phrase_str(self):
        result = self.store.lookup_phrase_str("so muong gat ngang")
        assert result is not None
        assert result == "số muỗng gạt ngang"

    def test_lookup_phrase_unknown(self):
        result = self.store.lookup_phrase("xyz xyz xyz")
        assert len(result) == 0

    def test_lookup_phrase_str_unknown(self):
        result = self.store.lookup_phrase_str("xyz xyz xyz")
        assert result is None

    def test_lookup_phrase_normalized(self):
        result = self.store.lookup_phrase_normalized("so muong gat ngang")
        assert len(result) > 0

    def test_lookup_phrase_normalized_unknown(self):
        result = self.store.lookup_phrase_normalized("xyz xyz xyz")
        assert len(result) == 0

    # -- OCR confusion -----------------------------------------------------

    def test_lookup_ocr_known(self):
        corrections = self.store.lookup_ocr("mùông")
        assert "muỗng" in corrections

    def test_lookup_ocr_unknown(self):
        corrections = self.store.lookup_ocr("xxxxxx")
        assert len(corrections) == 0

    def test_get_ocr_corrections(self):
        result = self.store.get_ocr_corrections("mùông")
        assert result.found
        assert any(c.text == "muỗng" for c in result.corrections)

    def test_get_all_ocr_confusions(self):
        confusions = self.store.get_all_ocr_confusions()
        assert "mùông" in confusions
        assert isinstance(confusions, dict)

    # -- Protected tokens --------------------------------------------------

    def test_protected_foreign_word(self):
        assert self.store.is_protected_token("DHA")

    def test_protected_abbreviation(self):
        assert self.store.is_protected_token("2pn")
        assert self.store.is_protected_token("dt")

    def test_not_protected_unknown(self):
        assert not self.store.is_protected_token("zzzzzzz")

    # -- Index -------------------------------------------------------------

    def test_get_lexicon_index(self):
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() > 0

    # -- Aggregate / statistics --------------------------------------------

    def test_get_abbreviation_entries(self):
        entries = self.store.get_abbreviation_entries()
        assert len(entries) > 0
        assert all(isinstance(e, AbbreviationEntry) for e in entries)

    def test_get_abbreviation_count(self):
        assert self.store.get_abbreviation_count() > 0

    def test_get_phrase_count(self):
        assert self.store.get_phrase_count() > 0

    def test_get_ocr_confusion_count(self):
        assert self.store.get_ocr_confusion_count() > 0

    def test_get_syllable_entry_count(self):
        assert self.store.get_syllable_entry_count() > 0

    def test_get_word_count(self):
        assert self.store.get_word_count() > 0

    def test_get_foreign_word_count(self):
        assert self.store.get_foreign_word_count() > 0


# ======================================================================
# LexiconDataStore tests
# ======================================================================


class TestLexiconDataStore(_StoreTestBase):
    def setup_method(self) -> None:
        self.store = LexiconDataStore.from_json()

    def test_from_json(self):
        store = LexiconDataStore.from_json()
        assert isinstance(store, LexiconDataStore)
        assert store.get_ocr_confusion_count() > 0

    def test_from_sqlite(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            store = LexiconDataStore.from_sqlite(Path(db_path))
            assert isinstance(store, LexiconDataStore)
            assert store.contains_syllable("muỗng")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)

    def test_from_json_and_sqlite(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_hybrid.db")
        try:
            _build_test_db(db_path)
            store = LexiconDataStore.from_json_and_sqlite(db_path=Path(db_path))
            assert isinstance(store, LexiconDataStore)
            assert store.contains_syllable("muỗng")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)

    def test_sqlite_entries_survive_db_deletion(self):
        """SQLite-loaded entries must still work after the DB file is removed."""
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            store = LexiconDataStore.from_sqlite(Path(db_path))
            # Delete the DB
            os.unlink(db_path)
            os.rmdir(db_dir)
            # Lookups must still work
            assert store.contains_syllable("muỗng")
            result = store.lookup_accentless("muong")
            assert result.found
        except Exception:
            # Clean up just in case
            if os.path.exists(db_path):
                os.unlink(db_path)
            if os.path.exists(db_dir):
                os.rmdir(db_dir)
            raise

    def test_json_does_not_load_trusted(self):
        """LexiconDataStore.from_json() should NOT load trusted words (those are in SQLite)."""
        word_count = self.store.get_word_count()
        assert word_count < 2000, (
            f"Expected <2000 words (only built-in JSON), got {word_count}. "
            f"Trusted words should only be loaded via from_sqlite."
        )

    def test_hybrid_loads_more_than_json_alone(self):
        """from_json_and_sqlite should have more words than JSON alone
        when the SQLite DB has additional trusted words.
        """
        # Use the production trusted_lexicon.db which has 80k+ words
        prod_db = Path("data/lexicon/trusted_lexicon.db")
        if prod_db.is_file():
            hybrid = LexiconDataStore.from_json_and_sqlite(db_path=prod_db)
            json_only = LexiconDataStore.from_json()
            assert hybrid.get_word_count() > json_only.get_word_count()

    def test_lookup_protected_token(self):
        assert self.store.is_protected_token("DHA")

    def test_lookup_syllable(self):
        candidates = self.store.lookup_syllable("muong")
        assert "muỗng" in candidates

    def test_accentless_lookup(self):
        result = self.store.lookup_accentless("muong")
        assert result.found

    def test_no_tone_lookup(self):
        result = self.store.lookup_no_tone("muong")
        assert result.found

    def test_ocr_lookup(self):
        corrections = self.store.lookup_ocr("mùông")
        assert "muỗng" in corrections

    def test_hybrid_get_lexicon_index(self):
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() > 0

    def test_load_default_backward_compat(self):
        """LexiconStore.load_default() should still work (deprecated alias)."""
        store = LexiconStore.load_default()
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")


# ======================================================================
# SqliteLexiconStore tests (created via from_sqlite)
# ======================================================================


class TestSqliteLexiconStoreFromBuiltin(_StoreTestBase):
    def setup_method(self) -> None:
        self._db_path = os.path.join(tempfile.mkdtemp(), "test_lexicon.db")
        _build_test_db(self._db_path)
        self.store = LexiconDataStore.from_sqlite(Path(self._db_path))

    def teardown_method(self) -> None:
        os.unlink(self._db_path)


class TestSqliteLexiconStoreFromPath:
    def test_load_default_is_lexicon_data_store(self):
        """LexiconStore.load_default() should return a LexiconDataStore."""
        store = LexiconStore.load_default()
        assert isinstance(store, LexiconDataStore)

    def test_load_default_contains_syllables(self):
        store = LexiconStore.load_default()
        assert store.contains_syllable("muỗng")

    def test_from_sqlite_reuses_existing_db(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            store1 = LexiconDataStore.from_sqlite(Path(db_path))
            store2 = LexiconDataStore.from_sqlite(Path(db_path))
            assert store2.get_syllable_entry_count() == store1.get_syllable_entry_count()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)


# ======================================================================
# load_default_lexicon factory tests
# ======================================================================


class TestLoadDefaultLexicon:
    def test_json_mode(self):
        store = load_default_lexicon("json")
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_sqlite_mode_raises_when_db_missing(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            load_default_lexicon("sqlite", db_path="/nonexistent/db.sqlite")

    def test_sqlite_mode_falls_back_to_json_when_requested(self):
        store = load_default_lexicon(
            "sqlite", db_path="/nonexistent/db.sqlite", fallback_to_json=True
        )
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_hybrid_mode_raises_when_db_missing(self):
        import pytest

        with pytest.raises(FileNotFoundError):
            load_default_lexicon("hybrid", db_path="/nonexistent/db.sqlite")

    def test_hybrid_mode_falls_back_when_requested(self):
        store = load_default_lexicon(
            "hybrid", db_path="/nonexistent/db.sqlite", fallback_to_json=True
        )
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_sqlite_with_builtin_db(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            store = load_default_lexicon("sqlite", db_path=db_path)
            assert isinstance(store, LexiconDataStore)
            assert store.contains_syllable("muỗng")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)

    def test_hybrid_with_builtin_db(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            store = load_default_lexicon("hybrid", db_path=db_path)
            assert isinstance(store, LexiconDataStore)
            assert store.contains_syllable("muỗng")
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)

    def test_memory_mode_equals_hybrid(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            _build_test_db(db_path)
            hybrid = load_default_lexicon("hybrid", db_path=db_path)
            memory = load_default_lexicon("memory", db_path=db_path)
            assert isinstance(hybrid, LexiconDataStore)
            assert isinstance(memory, LexiconDataStore)
            assert hybrid.get_syllable_entry_count() == memory.get_syllable_entry_count()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)
