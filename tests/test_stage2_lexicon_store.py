"""Tests for :mod:`vn_corrector.stage2_lexicon` store enhancements.

Covers new methods on the refactored stores:
- :meth:`~vn_corrector.stage2_lexicon.core.store.LexiconStore.is_protected_token`
- :meth:`~vn_corrector.stage2_lexicon.core.store.LexiconStore.get_lexicon_index`
"""

import os
import tempfile

from vn_corrector.stage2_lexicon import JsonLexiconStore, LexiconStore
from vn_corrector.stage2_lexicon.backends.sqlite_store import SqliteLexiconStore


class TestJsonLexiconStoreNewMethods:
    def setup_method(self) -> None:
        self.store = JsonLexiconStore.load_default()

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
        from vn_corrector.common.types import LexiconKind

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
        assert isinstance(store, JsonLexiconStore)
        assert store.contains_syllable("muỗng")


class TestSqliteLexiconStoreNewMethods:
    def setup_method(self) -> None:
        self._db_dir = tempfile.mkdtemp()
        self._db_path = os.path.join(self._db_dir, "test_lexicon.db")
        self.store = SqliteLexiconStore.from_builtin_resources(self._db_path, overwrite=True)

    def teardown_method(self) -> None:
        self.store.close()
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
    """Tests that ``load_default()`` loads the trusted word lexicon."""

    @classmethod
    def setup_class(cls) -> None:
        cls.store = JsonLexiconStore.load_default()

    def test_loads_trusted_entries(self):
        """load_default should include trusted word entries."""
        idx = self.store.get_lexicon_index()
        assert idx.total_entries() >= 80000, (
            f"Expected >=80000 entries with trusted lexicon, got {idx.total_entries()}"
        )

    def test_lookup_no_tone_returns_vietnamese_words(self):
        """lookup_no_tone should return accented forms from trusted lexicon."""
        result = self.store.lookup_no_tone("muong")
        assert result.found
        surfaces = [e.surface for e in result.entries]
        assert "muỗng" in surfaces, f"muỗng not in {surfaces}"

    def test_lookup_no_tone_so(self):
        """Common word "số" should be findable via "so"."""
        result = self.store.lookup_no_tone("so")
        assert result.found
        surfaces = [e.surface for e in result.entries]
        assert "số" in surfaces or "sô" in surfaces, f"số or sô not in {surfaces}"

    def test_lookup_accentless_duong(self):
        """đường should be findable via "duong"."""
        result = self.store.lookup_accentless("duong")
        assert result.found
        surfaces = [e.surface for e in result.entries]
        assert "đường" in surfaces, f"đường not in {surfaces}"

    def test_get_syllable_candidates_still_works(self):
        """Traditional syllable lookups should still work alongside trusted."""
        candidates = self.store.get_syllable_candidates("muong")
        assert len(candidates) >= 3
