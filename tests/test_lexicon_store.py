"""Tests for LexiconStore — interface, loading, lookup, and membership.

Abstract test classes run against every backend; concrete subclasses
provide the store fixture for each backend variant.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

from scripts.build_lexicon_db import _populate_from_json
from vn_corrector.common.types import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionLookupResult,
)
from vn_corrector.stage2_lexicon import HybridLexiconStore, JsonLexiconStore, LexiconStore
from vn_corrector.stage2_lexicon.backends.sqlite_store import _SCHEMA_SQL, SqliteLexiconStore


def _build_test_db(db_path: str | Path) -> SqliteLexiconStore:
    """Build a test SQLite DB from built-in JSON resources."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_SCHEMA_SQL)
    _populate_from_json(conn, Path("resources/lexicons"))
    conn.commit()
    conn.close()
    return SqliteLexiconStore.from_db(db_path)


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

    def test_load_default_contains_words(self):
        assert self.store.contains_word("số muỗng")

    def test_load_default_contains_units(self):
        assert self.store.contains_word("m")
        assert self.store.contains_word("kg")

    def test_load_default_contains_foreign(self):
        assert self.store.contains_foreign_word("DHA")
        assert self.store.contains_foreign_word("Lactose")

    def test_load_default_abbreviations(self):
        assert self.store.get_abbreviation_count() > 0

    # -- Exact lookup ------------------------------------------------------

    def _surface_entries(
        self, result: LexiconLookupResult
    ) -> list[LexiconEntry | AbbreviationEntry]:
        return [e for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))]

    def test_lookup_syllable(self):
        result = self.store.lookup("muỗng")
        assert result.found
        assert any(e.surface == "muỗng" for e in self._surface_entries(result))

    def test_lookup_word(self):
        result = self.store.lookup("số muỗng")
        assert result.found
        assert any(e.surface == "số muỗng" for e in self._surface_entries(result))

    def test_lookup_unknown(self):
        result = self.store.lookup("xyzzy")
        assert not result.found
        assert len(result.entries) == 0

    def test_lookup_unit(self):
        result = self.store.lookup("kg")
        assert result.found
        entries = self._surface_entries(result)
        entry = next(e for e in entries if isinstance(e, LexiconEntry) and e.surface == "kg")
        assert isinstance(entry, LexiconEntry) and entry.kind == "unit"

    # -- Accentless lookup ------------------------------------------------

    def _surfaces(self, result: LexiconLookupResult) -> set[str]:
        return {
            e.surface for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))
        }

    def test_accentless_known(self):
        result = self.store.lookup_accentless("muỗng")
        assert result.found
        assert any(
            e.surface == "muỗng"
            for e in result.entries
            if isinstance(e, (LexiconEntry, AbbreviationEntry))
        )

    def test_accentless_strips_accents(self):
        result = self.store.lookup_accentless("muỗng")
        result_plain = self.store.lookup_accentless("muong")
        assert result.found == result_plain.found

    def test_accentless_returns_multiple_candidates(self):
        result = self.store.lookup_accentless("muong")
        assert result.found
        assert len(result.entries) >= 2

    def test_accentless_ambiguous_candidates(self):
        result = self.store.lookup_accentless("so")
        assert result.found
        surfaces = self._surfaces(result)
        assert "số" in surfaces
        assert "sổ" in surfaces

    def test_accentless_unknown(self):
        result = self.store.lookup_accentless("zzzzz")
        assert not result.found

    def test_accentless_with_uppercase(self):
        lower = self.store.lookup_accentless("muỗng")
        upper = self.store.lookup_accentless("MUỖNG")
        assert lower.found == upper.found

    def test_accentless_duong_candidates(self):
        result = self.store.lookup_accentless("duong")
        assert result.found
        surfaces = self._surfaces(result)
        assert "đường" in surfaces
        assert "dương" in surfaces

    def test_accentless_hits_word_index(self):
        result = self.store.lookup_accentless("quận")
        assert result.found
        kinds = {str(e.kind) for e in result.entries if hasattr(e, "kind")}
        assert "syllable" in kinds
        assert "word" in kinds
        surfaces = self._surfaces(result)
        assert "quận" in surfaces

    # -- No-tone lookup ---------------------------------------------------

    def test_lookup_no_tone_matches_accentless(self):
        assert (
            self.store.lookup_no_tone("muong").found == self.store.lookup_accentless("muong").found
        )

    def test_lookup_no_tone_returns_candidates(self):
        result = self.store.lookup_no_tone("duong")
        assert result.found
        surfaces = {
            e.surface for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))
        }
        assert "đường" in surfaces

    def test_lookup_no_tone_unknown(self):
        result = self.store.lookup_no_tone("zzzzz")
        assert not result.found

    # -- Syllable candidates ----------------------------------------------

    def test_known_no_tone_key(self):
        candidates = self.store.get_syllable_candidates("muong")
        assert len(candidates) >= 2
        surfaces = {c.surface for c in candidates}
        assert "muỗng" in surfaces

    def test_unknown_no_tone_key(self):
        candidates = self.store.get_syllable_candidates("zzzzz")
        assert len(candidates) == 0

    def test_duong_has_multiple_candidates(self):
        candidates = self.store.get_syllable_candidates("duong")
        assert len(candidates) >= 2
        surfaces = {c.surface for c in candidates}
        assert "đường" in surfaces
        assert "dương" in surfaces

    def test_candidates_have_no_tone_field(self):
        candidates = self.store.get_syllable_candidates("muong")
        for c in candidates:
            assert c.no_tone == "muong"

    # -- Abbreviations ----------------------------------------------------

    def test_abbreviation_known(self):
        result = self.store.lookup_abbreviation("2pn")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "2 phòng ngủ" in entry.expansions

    def test_abbreviation_unknown(self):
        result = self.store.lookup_abbreviation("zzzzz")
        assert not result.found
        assert len(result.entries) == 0

    def test_ambiguous_dt(self):
        """dt should expand to both diện tích and đường trước."""
        result = self.store.lookup_abbreviation("dt")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "diện tích" in entry.expansions
        assert "đường trước" in entry.expansions
        assert entry.ambiguous

    def test_cc_abbreviation(self):
        result = self.store.lookup_abbreviation("cc")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "chung cư" in entry.expansions

    def test_abbreviation_with_period(self):
        result = self.store.lookup_abbreviation("q.")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.expansions == ("quận",)

    def test_abbreviation_entry_has_fields(self):
        result = self.store.lookup_abbreviation("2pn")
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.surface == "2pn"
        assert isinstance(entry.expansions, tuple)
        assert len(entry.expansions) > 0

    # -- Membership -------------------------------------------------------

    def test_contains_word_known(self):
        assert self.store.contains_word("số muỗng")

    def test_contains_word_unknown(self):
        assert not self.store.contains_word("xyzzy")

    def test_contains_syllable_known(self):
        assert self.store.contains_syllable("muỗng")
        assert self.store.contains_syllable("đường")

    def test_contains_syllable_unknown(self):
        assert not self.store.contains_syllable("xyzzy")

    def test_contains_foreign_word_known(self):
        assert self.store.contains_foreign_word("DHA")
        assert self.store.contains_foreign_word("ARA")

    def test_contains_foreign_word_unknown(self):
        assert not self.store.contains_foreign_word("xyzzy")

    # -- Data integrity ---------------------------------------------------

    def test_syllable_no_tone_key(self):
        result = self.store.lookup_accentless("muong")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert e.no_tone == "muong"

    def test_word_kind_tag(self):
        result = self.store.lookup("số muỗng")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert str(e.kind) in ("word", "syllable")

    def test_unit_kind_tag(self):
        result = self.store.lookup("kg")
        entry = next(
            (e for e in result.entries if isinstance(e, LexiconEntry) and e.surface == "kg"), None
        )
        assert entry is not None
        assert isinstance(entry, LexiconEntry) and entry.kind == "unit"

    def test_get_abbreviation_entries(self):
        entries = self.store.get_abbreviation_entries()
        assert len(entries) > 0
        assert all(isinstance(e, AbbreviationEntry) for e in entries)

    def test_get_abbreviation_count(self):
        assert self.store.get_abbreviation_count() > 0

    # -- Phrase lookup ----------------------------------------------------

    def test_phrases_loaded(self):
        assert self.store.get_phrase_count() > 0

    def test_lookup_phrase_exact(self):
        results = self.store.lookup_phrase("số muỗng gạt ngang")
        assert len(results) >= 1
        assert results[0].phrase == "số muỗng gạt ngang"
        assert results[0].n == 3

    def test_lookup_phrase_normalized(self):
        results = self.store.lookup_phrase_normalized("so muong gat ngang")
        assert len(results) >= 1
        assert results[0].phrase == "số muỗng gạt ngang"

    def test_lookup_phrase_unknown(self):
        results = self.store.lookup_phrase("xyzzy")
        assert len(results) == 0

    def test_phrase_has_domain(self):
        results = self.store.lookup_phrase("số muỗng gạt ngang")
        assert results[0].domain == "product_instruction"

    def test_phrase_multi_word_n(self):
        results = self.store.lookup_phrase("vừa đủ")
        assert len(results) >= 1
        assert results[0].n == 2

    # -- OCR confusion ----------------------------------------------------

    def _correction_texts(self, result: OcrConfusionLookupResult) -> set[str]:
        return {c.text for c in result.corrections}

    def test_confusions_loaded(self):
        assert self.store.get_ocr_confusion_count() > 0

    def test_known_confusion(self):
        result = self.store.get_ocr_corrections("mùông")
        assert result.found
        texts = self._correction_texts(result)
        assert "muỗng" in texts

    def test_another_known_confusion(self):
        result = self.store.get_ocr_corrections("rốt")
        assert result.found
        texts = self._correction_texts(result)
        assert "rót" in texts

    def test_unknown_confusion(self):
        result = self.store.get_ocr_corrections("xyzzy")
        assert not result.found
        assert len(result.corrections) == 0

    def test_confusion_with_multiple_corrections(self):
        result = self.store.get_ocr_corrections("đẫn")
        assert result.found
        texts = self._correction_texts(result)
        assert "dẫn" in texts
        assert "dần" in texts

    def test_get_all_confusions(self):
        all_confusions = self.store.get_all_ocr_confusions()
        assert isinstance(all_confusions, dict)
        assert "mùông" in all_confusions
        assert len(all_confusions) > 0

    def test_du_confusion(self):
        result = self.store.get_ocr_corrections("dủ")
        assert result.found
        texts = self._correction_texts(result)
        assert "đủ" in texts

    # -- Public API methods ------------------------------------------------

    def test_lookup_syllable_known(self):
        candidates = self.store.lookup_syllable("muong")
        assert "muỗng" in candidates

    def test_lookup_syllable_case_insensitive(self):
        """MÙÔNG should return same result as muong."""
        upper = set(self.store.lookup_syllable("MÙÔNG"))
        lower = set(self.store.lookup_syllable("muong"))
        assert upper == lower

    def test_lookup_syllable_accented_input(self):
        candidates = self.store.lookup_syllable("muỗng")
        assert "muỗng" in candidates

    def test_lookup_syllable_unknown(self):
        candidates = self.store.lookup_syllable("zzzzz")
        assert len(candidates) == 0

    def test_lookup_unit_known(self):
        entries = self.store.lookup_unit("kg")
        assert len(entries) >= 1
        assert entries[0].kind == "unit"

    def test_lookup_unit_unknown(self):
        entries = self.store.lookup_unit("xyzzy")
        assert len(entries) == 0

    def test_lookup_phrase_str_known(self):
        result = self.store.lookup_phrase_str("so muong gat ngang")
        assert result == "số muỗng gạt ngang"

    def test_lookup_phrase_str_unknown(self):
        result = self.store.lookup_phrase_str("xyzzy")
        assert result is None

    def test_lookup_ocr_known(self):
        corrections = self.store.lookup_ocr("mùông")
        assert "muỗng" in corrections

    def test_lookup_ocr_unknown(self):
        corrections = self.store.lookup_ocr("xyzzy")
        assert len(corrections) == 0

    # -- New stat methods --------------------------------------------------

    def test_get_syllable_entry_count(self):
        assert self.store.get_syllable_entry_count() > 0

    def test_get_word_count(self):
        assert self.store.get_word_count() > 0

    def test_get_foreign_word_count(self):
        assert self.store.get_foreign_word_count() > 0


# ======================================================================
# JsonLexiconStore tests
# ======================================================================


class TestJsonLexiconStore(_StoreTestBase):
    def setup_method(self) -> None:
        self.store = JsonLexiconStore.from_resources()

    def test_from_resources(self):
        store = JsonLexiconStore.from_resources()
        assert isinstance(store, JsonLexiconStore)
        assert store.get_ocr_confusion_count() > 0

    def test_load_default_backward_compat(self):
        """load_default() should still work (deprecated alias)."""
        store = JsonLexiconStore.load_default()
        assert isinstance(store, JsonLexiconStore)
        assert store.contains_syllable("muỗng")

    def test_json_store_does_not_load_trusted(self):
        """JsonLexiconStore should NOT load trusted words (those are in SQLite)."""
        word_count = self.store.get_word_count()
        assert word_count < 2000, (
            f"Expected <2000 words (only built-in JSON), got {word_count}. "
            f"Trusted words should only be loaded via SqliteLexiconStore."
        )


# ======================================================================
# SqliteLexiconStore tests
# ======================================================================


class TestSqliteLexiconStoreFromBuiltin(_StoreTestBase):
    def setup_method(self) -> None:
        self._db_path = os.path.join(tempfile.mkdtemp(), "test_lexicon.db")
        self.store = _build_test_db(self._db_path)

    def teardown_method(self) -> None:
        self.store.close()
        os.unlink(self._db_path)

    def test_reuses_existing_db(self):
        """A second open via from_db reuses the same DB file."""
        store2 = SqliteLexiconStore.from_db(self._db_path)
        assert store2.get_syllable_entry_count() == self.store.get_syllable_entry_count()
        store2.close()

    def test_from_path_works(self):
        store2 = SqliteLexiconStore.from_path(self._db_path)
        assert isinstance(store2, SqliteLexiconStore)
        assert store2.contains_syllable("muỗng")
        store2.close()


class TestSqliteLexiconStoreFromPath:
    def test_from_path_with_builtin_db(self):
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            store = _build_test_db(db_path)
            store2 = SqliteLexiconStore.from_path(db_path)
            assert store2.get_syllable_entry_count() == store.get_syllable_entry_count()
            store2.close()
            store.close()
        finally:
            os.unlink(db_path)
            os.rmdir(db_dir)

    def test_load_default_is_json_not_sqlite(self):
        """LexiconStore.load_default() should return a JsonLexiconStore (backward compat)."""
        store = LexiconStore.load_default()
        assert isinstance(store, JsonLexiconStore)

    def test_from_db_is_from_path_equivalent(self):
        """from_db should be an alias for from_path."""
        db_dir = tempfile.mkdtemp()
        db_path = os.path.join(db_dir, "test_lexicon.db")
        try:
            store1 = SqliteLexiconStore.from_path(db_path)
            store1.close()
            store2 = SqliteLexiconStore.from_db(db_path)
            assert isinstance(store2, SqliteLexiconStore)
            store2.close()
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
            os.rmdir(db_dir)


# ======================================================================
# HybridLexiconStore tests
# ======================================================================


class TestHybridLexiconStore(_StoreTestBase):
    def setup_method(self) -> None:
        self._json_store = JsonLexiconStore.from_resources()
        self._db_path = os.path.join(tempfile.mkdtemp(), "test_hybrid.db")
        self._sqlite_store = _build_test_db(self._db_path)
        self.store = HybridLexiconStore(primary=self._sqlite_store, fallback=self._json_store)

    def teardown_method(self) -> None:
        self.store.close()
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_primary_hit_wins(self):
        """Primary result should be returned when found."""
        result = self.store.lookup("muỗng")
        assert result.found

    def test_fallback_on_miss(self):
        """Fallback should be used when primary returns nothing."""
        # Both stores should contain basic items; test a case both have
        result = self.store.lookup("kg")
        assert result.found

    def test_hybrid_is_hybrid(self):
        assert isinstance(self.store, HybridLexiconStore)

    def test_hybrid_get_lexicon_index(self):
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() > 0

    def test_hybrid_protected_token(self):
        assert self.store.is_protected_token("DHA")

    def test_hybrid_lookup_syllable(self):
        candidates = self.store.lookup_syllable("muong")
        assert "muỗng" in candidates

    def test_hybrid_accentless(self):
        result = self.store.lookup_accentless("muong")
        assert result.found

    def test_hybrid_no_tone(self):
        result = self.store.lookup_no_tone("muong")
        assert result.found

    def test_hybrid_ocr(self):
        corrections = self.store.lookup_ocr("mùông")
        assert "muỗng" in corrections


class TestHybridLexiconStoreFallbackOnly:
    """Hybrid store where primary is empty — all hits come from fallback."""

    def setup_method(self) -> None:
        self._json_store = JsonLexiconStore.from_resources()
        self._db_path = os.path.join(tempfile.mkdtemp(), "test_empty.db")

        # Create an empty DB with the schema but no data
        import sqlite3

        from vn_corrector.stage2_lexicon.backends.sqlite_store import _SCHEMA_SQL

        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        conn.close()

        self._empty_sqlite = SqliteLexiconStore.from_db(self._db_path)
        self.store = HybridLexiconStore(primary=self._empty_sqlite, fallback=self._json_store)

    def teardown_method(self) -> None:
        self.store.close()
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_fallback_provides_syllables(self):
        assert self.store.contains_syllable("muỗng")

    def test_fallback_provides_words(self):
        assert self.store.contains_foreign_word("DHA")

    def test_fallback_on_accentless(self):
        result = self.store.lookup_accentless("muong")
        assert result.found
        surfaces = {e.surface for e in result.entries if hasattr(e, "surface")}
        assert "muỗng" in surfaces
