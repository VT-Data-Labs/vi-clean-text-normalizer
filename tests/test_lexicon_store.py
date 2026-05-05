"""Tests for LexiconStore — loading, lookup, and membership."""

from vn_corrector.common.types import AbbreviationEntry, LexiconEntry
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
    def test_lookup_syllable(self):
        store = LexiconStore.load_default()
        result = store.lookup("muỗng")
        assert result.found
        assert any(e.surface == "muỗng" for e in result.entries)

    def test_lookup_word(self):
        store = LexiconStore.load_default()
        result = store.lookup("số muỗng")
        assert result.found
        assert any(e.surface == "số muỗng" for e in result.entries)

    def test_lookup_unknown(self):
        store = LexiconStore.load_default()
        result = store.lookup("xyzzy")
        assert not result.found
        assert len(result.entries) == 0

    def test_lookup_unit(self):
        store = LexiconStore.load_default()
        result = store.lookup("kg")
        assert result.found
        entry = next(e for e in result.entries if isinstance(e, LexiconEntry) and e.surface == "kg")
        assert isinstance(entry, LexiconEntry) and entry.kind == "unit"


class TestAccentlessLookup:
    def test_accentless_known(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muỗng")
        assert result.found
        assert any(e.surface == "muỗng" for e in result.entries)

    def test_accentless_strips_accents(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muỗng")
        result_plain = store.lookup_accentless("muong")
        assert result.found == result_plain.found

    def test_accentless_returns_multiple_candidates(self):
        store = LexiconStore.load_default()
        # "muong" has multiple forms: muỗng, mường, muông, muống, muồng, mượng
        result = store.lookup_accentless("muong")
        assert result.found
        assert len(result.entries) >= 2

    def test_accentless_ambiguous_candidates(self):
        store = LexiconStore.load_default()
        # "so" has multiple forms: số, sổ, sờ, sơ, sợ, sở
        result = store.lookup_accentless("so")
        assert result.found
        surfaces = {e.surface for e in result.entries}
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
        # "duong" has: đường, dương, duỗng, duồng, đượng
        result = store.lookup_accentless("duong")
        assert result.found
        surfaces = {e.surface for e in result.entries}
        assert "đường" in surfaces
        assert "dương" in surfaces


class TestLookupNoTone:
    def test_lookup_no_tone_matches_accentless(self):
        store = LexiconStore.load_default()
        assert store.lookup_no_tone("muong").found == store.lookup_accentless("muong").found

    def test_lookup_no_tone_returns_candidates(self):
        store = LexiconStore.load_default()
        result = store.lookup_no_tone("duong")
        assert result.found
        surfaces = {e.surface for e in result.entries}
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
        assert entry.expansions == ["quận"]

    def test_abbreviation_entry_has_fields(self):
        store = LexiconStore.load_default()
        result = store.lookup_abbreviation("2pn")
        entry = result.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.surface == "2pn"
        assert isinstance(entry.expansions, list)
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
    def test_syllable_normalized_key(self):
        store = LexiconStore.load_default()
        result = store.lookup_accentless("muong")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert e.normalized == "muong"

    def test_word_kind_tag(self):
        store = LexiconStore.load_default()
        result = store.lookup("số muỗng")
        for e in result.entries:
            if isinstance(e, LexiconEntry):
                assert e.kind in ("common_word", "phrase", "syllable")

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
