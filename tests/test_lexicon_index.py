"""Tests for :class:`~vn_corrector.stage2_lexicon.core.types.LexiconIndex`."""

from vn_corrector.common.enums import LexiconKind
from vn_corrector.common.scoring import Score
from vn_corrector.lexicon.types import LexiconEntry, Provenance
from vn_corrector.stage2_lexicon.core.types import LexiconIndex


class _Factory:
    """Helper to create test entries."""

    @staticmethod
    def make(surface: str, no_tone: str, kind: LexiconKind = LexiconKind.SYLLABLE) -> LexiconEntry:
        return LexiconEntry(
            entry_id=f"test/{surface}",
            surface=surface,
            normalized=surface,
            no_tone=no_tone,
            kind=kind,
            score=Score(confidence=0.5, frequency=0.5),
            provenance=Provenance(),
        )


class TestLexiconIndex:
    def test_empty_index(self):
        idx = LexiconIndex()
        assert idx.total_entries() == 0

    def test_build_empty(self):
        idx = LexiconIndex.build([])
        assert idx.total_entries() == 0

    def test_build_single_entry(self):
        e = _Factory.make("muỗng", "muong")
        idx = LexiconIndex.build([e])
        assert idx.total_entries() == 1
        assert len(idx.by_surface["muỗng"]) == 1
        assert len(idx.by_normalized["muong"]) == 1
        assert len(idx.by_kind[LexiconKind.SYLLABLE]) == 1

    def test_build_multiple_entries(self):
        entries = [
            _Factory.make("muỗng", "muong"),
            _Factory.make("mường", "muong"),
            _Factory.make("muông", "muong"),
        ]
        idx = LexiconIndex.build(entries)
        assert idx.total_entries() == 3
        assert len(idx.by_normalized["muong"]) == 3

    def test_build_different_kinds(self):
        entries = [
            _Factory.make("muỗng", "muong", LexiconKind.SYLLABLE),
            _Factory.make("số muỗng", "so muong", LexiconKind.WORD),
        ]
        idx = LexiconIndex.build(entries)
        assert idx.total_entries() == 2
        assert len(idx.by_kind[LexiconKind.SYLLABLE]) == 1
        assert len(idx.by_kind[LexiconKind.WORD]) == 1

    def test_entries_by_surface(self):
        e = _Factory.make("muỗng", "muong")
        idx = LexiconIndex.build([e])
        results = idx.entries_by_surface("muỗng")
        assert len(results) == 1
        assert results[0].surface == "muỗng"

    def test_entries_by_surface_missing(self):
        idx = LexiconIndex.build([])
        assert idx.entries_by_surface("xyzzy") == []

    def test_entries_by_normalized(self):
        e = _Factory.make("muỗng", "muong")
        idx = LexiconIndex.build([e])
        results = idx.entries_by_normalized("muong")
        assert len(results) == 1
        assert results[0].no_tone == "muong"

    def test_entries_by_normalized_returns_all_forms(self):
        entries = [
            _Factory.make("muỗng", "muong"),
            _Factory.make("mường", "muong"),
        ]
        idx = LexiconIndex.build(entries)
        results = idx.entries_by_normalized("muong")
        assert len(results) == 2

    def test_entries_by_kind(self):
        e = _Factory.make("muỗng", "muong", LexiconKind.SYLLABLE)
        idx = LexiconIndex.build([e])
        results = idx.entries_by_kind(LexiconKind.SYLLABLE)
        assert len(results) == 1
        assert results[0].kind == LexiconKind.SYLLABLE

    def test_entries_by_kind_empty(self):
        idx = LexiconIndex.build([])
        assert idx.entries_by_kind(LexiconKind.WORD) == []

    def test_build_with_duplicate_surfaces(self):
        """Multiple entries can share the same surface (e.g. same word, different domain)."""
        e1 = _Factory.make("test", "test", LexiconKind.WORD)
        e2 = _Factory.make("test", "test", LexiconKind.DOMAIN_TERM)
        idx = LexiconIndex.build([e1, e2])
        assert len(idx.by_surface["test"]) == 2
