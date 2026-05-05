"""Tests for :func:`~vn_corrector.stage2_lexicon.core.normalize.normalize_key`."""

from vn_corrector.stage2_lexicon.core.normalize import normalize_key


class TestNormalizeKey:
    """Canonical key — the backbone of the lexicon system.

    Invariant::

        normalize_key("Muỗng") == normalize_key("muong")  # → "muong"
    """

    def test_lowercase(self):
        assert normalize_key("MUỖNG") == "muong"

    def test_strip_accents(self):
        assert normalize_key("muỗng") == "muong"
        assert normalize_key("đường") == "duong"
        assert normalize_key("dương") == "duong"

    def test_invariant_muong(self):
        """normalize_key("Muỗng") == normalize_key("muong")"""
        assert normalize_key("Muỗng") == normalize_key("muong")

    def test_invariant_duong(self):
        """normalize_key("Đường") == normalize_key("duong")"""
        assert normalize_key("Đường") == normalize_key("duong")

    def test_whitespace_normalized(self):
        assert normalize_key("  số   muỗng  ") == "so muong"

    def test_empty_string(self):
        assert normalize_key("") == ""

    def test_whitespace_only(self):
        assert normalize_key("   ") == ""

    def test_phrase(self):
        assert normalize_key("SỐ MUỖNG GẠT NGANG") == "so muong gat ngang"

    def test_numbers_preserved(self):
        assert normalize_key("120ml") == "120ml"
        assert normalize_key("2'-FL") == "2'-fl"

    def test_mixed_language(self):
        assert normalize_key("DHA và ARA") == "dha va ara"

    def test_accentless_input(self):
        """Ac centless input stays unchanged."""
        assert normalize_key("muong") == "muong"

    def test_dd_stripping(self):
        assert normalize_key("Đà Nẵng") == "da nang"
        assert normalize_key("đủ") == "du"
        assert normalize_key("ĐỦ") == "du"
