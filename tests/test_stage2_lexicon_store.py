"""Tests for :mod:`vn_corrector.stage2_lexicon` store enhancements.

Covers new methods on the refactored stores:
- :meth:`~vn_corrector.stage2_lexicon.core.store.LexiconStore.is_protected_token`
- :meth:`~vn_corrector.stage2_lexicon.core.store.LexiconStore.get_lexicon_index`
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from scripts.build_trusted_lexicon_db import (
    _populate_from_json,
    _populate_trusted_jsonl,
)
from vn_corrector.stage2_lexicon import LexiconDataStore, LexiconStore
from vn_corrector.stage2_lexicon.backends import _SCHEMA_SQL


def _build_test_db(db_path: str | Path) -> None:
    """Build a test SQLite DB from built-in JSON resources."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    _populate_from_json(conn, Path("resources/lexicons"))
    conn.commit()
    conn.close()


class TestLexiconDataStoreNewMethods:
    def setup_method(self) -> None:
        self.store = LexiconDataStore.from_json()

    # -- is_protected_token -----------------------------------------------

    def test_protected_foreign_word(self):
        assert self.store.is_protected_token("DHA")
        assert self.store.is_protected_token("ARA")

    def test_protected_abbreviation(self):
        assert self.store.is_protected_token("2pn")
        assert self.store.is_protected_token("dt")

    def test_not_protected_regular_word(self):
        assert not self.store.is_protected_token("muỗng")
        assert not self.store.is_protected_token("số muỗng")

    def test_not_protected_empty(self):
        assert not self.store.is_protected_token("")
        assert not self.store.is_protected_token("   ")

    def test_not_protected_unknown(self):
        assert not self.store.is_protected_token("xyzzy")

    # -- get_lexicon_index ------------------------------------------------

    def test_index_is_returned(self):
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() > 0
        assert idx.by_surface is not None
        assert idx.by_normalized is not None
        assert idx.by_kind is not None

    def test_index_contains_known_entry(self):
        idx = self.store.get_lexicon_index()
        entries = idx.entries_by_surface("muỗng")
        assert len(entries) >= 1
        assert entries[0].surface == "muỗng"

    def test_index_by_kind_contains_syllables(self):
        from vn_corrector.common.enums import LexiconKind

        idx = self.store.get_lexicon_index()
        syllables = idx.entries_by_kind(LexiconKind.SYLLABLE)
        assert len(syllables) > 0
        assert all(e.kind == LexiconKind.SYLLABLE for e in syllables)

    def test_index_by_normalized(self):
        idx = self.store.get_lexicon_index()
        entries = idx.entries_by_normalized("muong")
        assert len(entries) >= 2  # muỗng, mường, etc.

    # -- data property ----------------------------------------------------

    def test_data_property(self):
        assert len(self.store.data) > 0
        assert all(hasattr(e, "surface") for e in self.store.data)

    def test_index_property(self):
        assert self.store.index.total_entries() == len(self.store.data)

    # -- Backward compatibility -------------------------------------------

    def test_lookup_still_works(self):
        result = self.store.lookup("muỗng")
        assert result.found

    def test_lookup_accentless_still_works(self):
        result = self.store.lookup_accentless("muong")
        assert result.found

    def test_contains_syllable_still_works(self):
        assert self.store.contains_syllable("muỗng")

    def test_contains_word_still_works(self):
        assert self.store.contains_word("kg")

    def test_contains_foreign_word_still_works(self):
        assert self.store.contains_foreign_word("DHA")

    def test_get_abbreviation_count(self):
        assert self.store.get_abbreviation_count() > 0

    def test_get_phrase_count(self):
        assert self.store.get_phrase_count() > 0

    def test_get_ocr_confusion_count(self):
        assert self.store.get_ocr_confusion_count() > 0

    def test_lookup_ocr(self):
        corrections = self.store.lookup_ocr("mùông")
        assert "muỗng" in corrections

    def test_lookup_abbreviation(self):
        result = self.store.lookup_abbreviation("2pn")
        assert result.found

    def test_lookup_phrase(self):
        results = self.store.lookup_phrase("số muỗng gạt ngang")
        assert len(results) >= 1

    def test_phrase_str(self):
        assert self.store.lookup_phrase_str("so muong gat ngang") == "số muỗng gạt ngang"

    def test_get_syllable_candidates(self):
        candidates = self.store.get_syllable_candidates("muong")
        assert len(candidates) >= 2

    def test_get_all_ocr_confusions(self):
        confusions = self.store.get_all_ocr_confusions()
        assert "mùông" in confusions

    def test_get_ocr_corrections(self):
        result = self.store.get_ocr_corrections("mùông")
        assert result.found

    def test_get_syllable_entry_count(self):
        assert self.store.get_syllable_entry_count() > 0

    def test_get_word_count(self):
        assert self.store.get_word_count() > 0

    def test_get_foreign_word_count(self):
        assert self.store.get_foreign_word_count() > 0

    def test_get_abbreviation_entries(self):
        entries = self.store.get_abbreviation_entries()
        assert len(entries) > 0

    def test_load_default_classmethod(self):
        store = LexiconStore.load_default()
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")


class TestLexiconDataStoreFromSqlite:
    def setup_method(self) -> None:
        self._db_dir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._db_dir, "test_lexicon.db")
        _build_test_db(self._db_path)
        self.store = LexiconDataStore.from_sqlite(Path(self._db_path))

    def teardown_method(self) -> None:
        os.unlink(self._db_path)
        os.rmdir(self._db_dir)

    def test_protected_foreign_word(self):
        assert self.store.is_protected_token("DHA")
        assert self.store.is_protected_token("ARA")

    def test_protected_abbreviation(self):
        assert self.store.is_protected_token("2pn")

    def test_not_protected_regular_word(self):
        assert not self.store.is_protected_token("muỗng")

    def test_get_lexicon_index(self):
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() > 0
        entries = idx.entries_by_surface("muỗng")
        assert len(entries) >= 1

    def test_lookup_still_works(self):
        result = self.store.lookup("muỗng")
        assert result.found

    def test_contains_word_still_works(self):
        assert self.store.contains_word("kg")


class TestTrustedLexiconIntegration:
    """Tests that trusted words compile into SQLite with normal lookup behavior.

    Trusted words are NOT loaded into the JSON store — they are compiled into
    the SQLite DB and loaded into ``LexiconDataStore`` via ``load_sqlite()``.
    """

    def setup_method(self) -> None:
        self._db_dir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._db_dir, "test_trusted.db")
        self._jsonl_path = os.path.join(self._db_dir, "test_trusted.jsonl")

        # Write a small trusted JSONL
        trusted_entries = [
            {
                "surface": "trường học",
                "normalized": "truong hoc",
                "no_tone": "truong hoc",
                "kind": "word",
                "score": {"confidence": 0.95, "frequency": 0.8},
                "provenance": {"source": "external-dictionary", "source_name": "test"},
                "tags": ["trusted"],
            },
            {
                "surface": "người dùng",
                "normalized": "nguoi dung",
                "no_tone": "nguoi dung",
                "kind": "word",
                "score": {"confidence": 0.98, "frequency": 0.9},
                "provenance": {"source": "external-dictionary", "source_name": "test"},
                "tags": ["trusted"],
            },
        ]
        with open(self._jsonl_path, "w", encoding="utf-8") as f:
            for entry in trusted_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Build a SQLite DB from built-in resources + trusted JSONL
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SCHEMA_SQL)
        _populate_from_json(conn, Path("resources/lexicons"))
        _populate_trusted_jsonl(conn, self._jsonl_path)
        conn.commit()
        conn.close()

        self.store = LexiconDataStore.from_sqlite(Path(self._db_path))

    def teardown_method(self) -> None:
        os.unlink(self._jsonl_path)
        os.unlink(self._db_path)
        os.rmdir(self._db_dir)

    def test_trusted_words_accessible_via_lookup(self):
        """Trusted words should be findable via normal word lookup."""
        result = self.store.lookup("trường học")
        assert result.found, "Trusted word should be found via lookup"
        surfaces = {e.surface for e in result.entries if hasattr(e, "surface")}
        assert "trường học" in surfaces

    def test_trusted_words_accessible_via_accentless(self):
        """Trusted words should be findable via accentless/no_tone lookup."""
        result = self.store.lookup_accentless("truong hoc")
        assert result.found, "Trusted word should be found via accentless lookup"
        surfaces = {e.surface for e in result.entries if hasattr(e, "surface")}
        assert "trường học" in surfaces

    def test_trusted_words_accessible_via_no_tone(self):
        result = self.store.lookup_no_tone("nguoi dung")
        assert result.found
        surfaces = {e.surface for e in result.entries if hasattr(e, "surface")}
        assert "người dùng" in surfaces

    def test_trusted_words_contained(self):
        assert self.store.contains_word("trường học")

    def test_json_store_does_not_have_trusted_words(self):
        """LexiconDataStore.from_json() should NOT contain trusted words."""
        json_store = LexiconDataStore.from_json()
        assert not json_store.contains_word("trường học"), (
            "Trusted words should NOT be in JSON-only store"
        )


# ======================================================================
# load_default_lexicon factory tests
# ======================================================================


class TestLoadDefaultLexiconFactory:
    def test_json_mode(self):
        from vn_corrector.stage2_lexicon import LexiconDataStore, load_default_lexicon

        store = load_default_lexicon("json")
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_sqlite_mode_raises_when_db_missing(self):
        import pytest

        from vn_corrector.stage2_lexicon import load_default_lexicon

        with pytest.raises(FileNotFoundError):
            load_default_lexicon("sqlite", db_path="/nonexistent/db.sqlite")

    def test_sqlite_mode_falls_back_to_json_when_requested(self):
        from vn_corrector.stage2_lexicon import LexiconDataStore, load_default_lexicon

        store = load_default_lexicon(
            "sqlite", db_path="/nonexistent/db.sqlite", fallback_to_json=True
        )
        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_hybrid_mode_raises_when_db_missing(self):
        import pytest

        from vn_corrector.stage2_lexicon import load_default_lexicon

        with pytest.raises(FileNotFoundError):
            load_default_lexicon("hybrid", db_path="/nonexistent/db.sqlite")

    def test_hybrid_mode_falls_back_when_requested(self):
        from vn_corrector.stage2_lexicon import LexiconDataStore, load_default_lexicon

        store = load_default_lexicon(
            "hybrid", db_path="/nonexistent/db.sqlite", fallback_to_json=True
        )

        assert isinstance(store, LexiconDataStore)
        assert store.contains_syllable("muỗng")

    def test_sqlite_with_builtin_db(self):
        from vn_corrector.stage2_lexicon import LexiconDataStore, load_default_lexicon

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
        from vn_corrector.stage2_lexicon import LexiconDataStore, load_default_lexicon

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
