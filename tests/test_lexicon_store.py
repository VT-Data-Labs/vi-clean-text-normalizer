"""Tests for LexiconStore — loading, lookup, and membership."""

from vn_corrector.common.types import (
    AbbreviationEntry,
    LexiconEntry,
    LexiconLookupResult,
    OcrConfusionLookupResult,
)
from vn_corrector.lexicon.store import LexiconStore


class TestLexiconStoreLoad:
    def test_load_default(self):
        store = LexiconStore.load_default()
        assert isinstance(store, LexiconStore)

    def test_load_default_contains_syllables(self):
        store = LexiconStore.load_default()
        # Known syllable
        assert store.contains_syllable("muỗng")

    def test_load_default_contains_words(self):
        store = LexiconStore.load_default()
        # Known word
        assert store.contains_word("số muỗng")

    def test_load_default_contains_units(self):
        store = LexiconStore.load_default()
        assert store.contains_word("m")
        assert store.contains_word("kg")

    def test_load_default_contains_foreign(self):
        store = LexiconStore.load_default()
        assert store.contains_foreign_word("DHA")
        assert store.contains_foreign_word("Lactose")

    def test_load_default_abbreviations(self):
        store = LexiconStore.load_default()
        assert store.get_abbreviation_count() > 0


class TestExactLookup:
    def _surface_entries(
        self, result: LexiconLookupResult
    ) -> list[LexiconEntry | AbbreviationEntry]:
        return [e for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))]

    def test_lookup_syllable(self):
        store = LexiconStore.load_default()
        result = store.lookup("muỗng")
        assert result.found
        assert any(e.surface == "muỗng" for e in self._surface_entries(result))

    def test_lookup_word(self):
        store = LexiconStore.load_default()
        result = store.lookup("số muỗng")
        assert result.found
        assert any(e.surface == "số muỗng" for e in self._surface_entries(result))

    def test_lookup_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup("xyzzy")
        assert not result.found
        assert len(result.entries) == 0

    def test_lookup_unit(self):
        store = LexiconStore.load_default()
        result = store.lookup("kg")
        assert result.found
        entries = self._surface_entries(result)
        entry = next(e for e in entries if isinstance(e, LexiconEntry) and e.surface == "kg")
        assert isinstance(entry, LexiconEntry) and entry.kind == "unit"


class TestAccentlessLookup:
    def _surfaces(self, result: LexiconLookupResult) -> set[str]:
        return {
            e.surface for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))
        }

    def test_accentless_known(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muỗng")
        assert result.found
        assert any(
            e.surface == "muỗng"
            for e in result.entries
            if isinstance(e, (LexiconEntry, AbbreviationEntry))
        )

    def test_accentless_strips_accents(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muỗng")
        result_plain = store.lookup_accentless("muong")
        assert result.found == result_plain.found

    def test_accentless_returns_multiple_candidates(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muong")
        assert result.found
        assert len(result.entries) >= 2

    def test_accentless_ambiguous_candidates(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("so")
        assert result.found
        surfaces = self._surfaces(result)
        assert "số" in surfaces
        assert "sổ" in surfaces

    def test_accentless_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("zzzzz")
        assert not result.found

    def test_accentless_with_uppercase(self):
        store = LexiconStore.load_default()
        lower = store.lookup_accentless("muỗng")
        upper = store.lookup_accentless("MUỖNG")
        assert lower.found == upper.found

    def test_accentless_duong_candidates(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("duong")
        assert result.found
        surfaces = self._surfaces(result)
        assert "đường" in surfaces
        assert "dương" in surfaces

    def test_accentless_hits_word_index(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("quận")
        assert result.found
        kinds = {str(e.kind) for e in result.entries if hasattr(e, "kind")}
        assert "syllable" in kinds
        assert "word" in kinds
        surfaces = self._surfaces(result)
        assert "quận" in surfaces


class TestLookupNoTone:
    def test_lookup_no_tone_matches_accentless(self):
        store = LexiconStore.load_default()
        assert store.lookup_no_tone("muong").found == store.lookup_accentless("muong").found

    def test_lookup_no_tone_returns_candidates(self):
        store = LexiconStore.load_default()
        result = store.lookup_no_tone("duong")
        assert result.found
        surfaces = {
            e.surface for e in result.entries if isinstance(e, (LexiconEntry, AbbreviationEntry))
        }
        assert "đường" in surfaces

    def test_lookup_no_tone_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup_no_tone("zzzzz")
        assert not result.found


class TestGetSyllableCandidates:
    def test_known_no_tone_key(self):
        store = LexiconStore.load_default()
        candidates = store.get_syllable_candidates("muong")
        assert len(candidates) >= 2
        surfaces = {c.surface for c in candidates}
        assert "muỗng" in surfaces

    def test_unknown_no_tone_key(self):
        store = LexiconStore.load_default()
        candidates = store.get_syllable_candidates("zzzzz")
        assert len(candidates) == 0

    def test_duong_has_multiple_candidates(self):
        store = LexiconStore.load_default()
        candidates = store.get_syllable_candidates("duong")
        assert len(candidates) >= 2
        surfaces = {c.surface for c in candidates}
        assert "đường" in surfaces
        assert "dương" in surfaces

    def test_candidates_have_no_tone_field(self):
        store = LexiconStore.load_default()
        candidates = store.get_syllable_candidates("muong")
        for c in candidates:
            assert c.no_tone == "muong"


class TestAbbreviationLookup:
    def test_abbreviation_known(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("2pn")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "2 phòng ngủ" in entry.expansions

    def test_abbreviation_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("zzzzz")
        assert not result.found
        assert len(result.entries) == 0

    def test_ambiguous_dt(self):
        """dt should expand to both diện tích and đường trước."""
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("dt")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "diện tích" in entry.expansions
        assert "đường trước" in entry.expansions
        assert entry.ambiguous

    def test_cc_abbreviation(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("cc")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert "chung cư" in entry.expansions

    def test_abbreviation_with_period(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("q.")
        assert result.found
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.expansions == ("quận",)

    def test_abbreviation_entry_has_fields(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("2pn")
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.surface == "2pn"
        assert isinstance(entry.expansions, tuple)
        assert len(entry.expansions) > 0


class TestMembership:
    def test_contains_word_known(self):
        store = LexiconStore.load_default()
        assert store.contains_word("số muỗng")

    def test_contains_word_unknown(self):
        store = LexiconStore.load_default()
        assert not store.contains_word("xyzzy")

    def test_contains_syllable_known(self):
        store = LexiconStore.load_default()
        assert store.contains_syllable("muỗng")
        assert store.contains_syllable("đường")

    def test_contains_syllable_unknown(self):
        store = LexiconStore.load_default()
        assert not store.contains_syllable("xyzzy")

    def test_contains_foreign_word_known(self):
        store = LexiconStore.load_default()
        assert store.contains_foreign_word("DHA")
        assert store.contains_foreign_word("ARA")

    def test_contains_foreign_word_unknown(self):
        store = LexiconStore.load_default()
        assert not store.contains_foreign_word("xyzzy")


class TestDataIntegrity:
    def test_syllable_no_tone_key(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muong")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert e.no_tone == "muong"

    def test_word_kind_tag(self):
        store = LexiconStore.load_default()
        result = store.lookup("số muỗng")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert str(e.kind) in ("word", "syllable")

    def test_unit_kind_tag(self):
        store = LexiconStore.load_default()
        result = store.lookup("kg")
        entry = next(
            (e for e in result.entries if isinstance(e, LexiconEntry) and e.surface == "kg"), None
        )
        assert entry is not None
        assert isinstance(entry, LexiconEntry) and entry.kind == "unit"

    def test_get_abbreviation_entries(self):
        store = LexiconStore.load_default()
        entries = store.get_abbreviation_entries()
        assert len(entries) > 0
        assert all(isinstance(e, AbbreviationEntry) for e in entries)

    def test_get_abbreviation_count(self):
        store = LexiconStore.load_default()
        assert store.get_abbreviation_count() > 0


class TestPhraseLookup:
    def test_phrases_loaded(self):
        store = LexiconStore.load_default()
        assert store.get_phrase_count() > 0

    def test_lookup_phrase_exact(self):
        store = LexiconStore.load_default()
        results = store.lookup_phrase("số muỗng gạt ngang")
        assert len(results) >= 1
        assert results[0].phrase == "số muỗng gạt ngang"
        assert results[0].n == 3

    def test_lookup_phrase_normalized(self):
        store = LexiconStore.load_default()
        results = store.lookup_phrase_normalized("so muong gat ngang")
        assert len(results) >= 1
        assert results[0].phrase == "số muỗng gạt ngang"

    def test_lookup_phrase_unknown(self):
        store = LexiconStore.load_default()
        results = store.lookup_phrase("xyzzy")
        assert len(results) == 0

    def test_phrase_has_domain(self):
        store = LexiconStore.load_default()
        results = store.lookup_phrase("số muỗng gạt ngang")
        assert results[0].domain == "product_instruction"

    def test_phrase_multi_word_n(self):
        store = LexiconStore.load_default()
        results = store.lookup_phrase("vừa đủ")
        assert len(results) >= 1
        assert results[0].n == 2


class TestOcrConfusionLookup:
    def _correction_texts(self, result: OcrConfusionLookupResult) -> set[str]:
        return {c.text for c in result.corrections}

    def test_confusions_loaded(self):
        store = LexiconStore.load_default()
        assert store.get_ocr_confusion_count() > 0

    def test_known_confusion(self):
        store = LexiconStore.load_default()
        result = store.get_ocr_corrections("mùông")
        assert result.found
        texts = self._correction_texts(result)
        assert "muỗng" in texts

    def test_another_known_confusion(self):
        store = LexiconStore.load_default()
        result = store.get_ocr_corrections("rốt")
        assert result.found
        texts = self._correction_texts(result)
        assert "rót" in texts

    def test_unknown_confusion(self):
        store = LexiconStore.load_default()
        result = store.get_ocr_corrections("xyzzy")
        assert not result.found
        assert len(result.corrections) == 0

    def test_confusion_with_multiple_corrections(self):
        store = LexiconStore.load_default()
        result = store.get_ocr_corrections("đẫn")
        assert result.found
        texts = self._correction_texts(result)
        assert "dẫn" in texts
        assert "dần" in texts

    def test_get_all_confusions(self):
        store = LexiconStore.load_default()
        all_confusions = store.get_all_ocr_confusions()
        assert isinstance(all_confusions, dict)
        assert "mùông" in all_confusions
        assert len(all_confusions) > 0

    def test_du_confusion(self):
        store = LexiconStore.load_default()
        result = store.get_ocr_corrections("dủ")
        assert result.found
        texts = self._correction_texts(result)
        assert "đủ" in texts


class TestPublicAPI:
    """Tests for the simplified public API methods."""

    def test_lookup_syllable_known(self):
        store = LexiconStore.load_default()
        candidates = store.lookup_syllable("muong")
        assert "muỗng" in candidates

    def test_lookup_syllable_case_insensitive(self):
        """'MÙÔNG' should return same result as 'muong'."""
        store = LexiconStore.load_default()
        upper = set(store.lookup_syllable("MÙÔNG"))
        lower = set(store.lookup_syllable("muong"))
        assert upper == lower

    def test_lookup_syllable_accented_input(self):
        """Accented input 'muỗng' should still look up by no-tone key."""
        store = LexiconStore.load_default()
        candidates = store.lookup_syllable("muỗng")
        assert "muỗng" in candidates

    def test_lookup_syllable_unknown(self):
        store = LexiconStore.load_default()
        candidates = store.lookup_syllable("zzzzz")
        assert len(candidates) == 0

    def test_lookup_unit_known(self):
        store = LexiconStore.load_default()
        entries = store.lookup_unit("kg")
        assert len(entries) >= 1
        assert entries[0].kind == "unit"

    def test_lookup_unit_unknown(self):
        store = LexiconStore.load_default()
        entries = store.lookup_unit("xyzzy")
        assert len(entries) == 0

    def test_lookup_phrase_str_known(self):
        store = LexiconStore.load_default()
        result = store.lookup_phrase_str("so muong gat ngang")
        assert result == "số muỗng gạt ngang"

    def test_lookup_phrase_str_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup_phrase_str("xyzzy")
        assert result is None

    def test_lookup_ocr_known(self):
        store = LexiconStore.load_default()
        corrections = store.lookup_ocr("mùông")
        assert "muỗng" in corrections

    def test_lookup_ocr_unknown(self):
        store = LexiconStore.load_default()
        corrections = store.lookup_ocr("xyzzy")
        assert len(corrections) == 0

    def test_load_classmethod(self):
        store = LexiconStore.load()
        assert isinstance(store, LexiconStore)
        assert store.get_ocr_confusion_count() > 0
