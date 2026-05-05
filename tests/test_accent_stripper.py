"""Tests for Vietnamese accent stripping."""

from vn_corrector.stage2_lexicon.core.accent_stripper import (
    VIETNAMESE_ACCENT_MAP,
    strip_accents,
    strip_accents_preserve_case,
    strip_vietnamese_accents,
    to_no_tone_key,
)


class TestStripAccents:
    def test_dd_lowercase(self):
        assert strip_accents("đ") == "d"

    def test_dd_uppercase(self):
        assert strip_accents("Đ") == "d"

    def test_dd_in_word(self):
        assert strip_accents("đường") == "duong"

    def test_dd_uppercase_word(self):
        assert strip_accents("ĐƯỜNG") == "duong"

    def test_vietnamese_tone_marks(self):
        assert strip_accents("số") == "so"
        assert strip_accents("muỗng") == "muong"
        assert strip_accents("mường") == "muong"
        assert strip_accents("dương") == "duong"

    def test_vietnamese_phrase(self):
        assert strip_accents("RÓT NƯỚC") == "rot nuoc"

    def test_vietnamese_sentence(self):
        text = "LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ"
        expected = "lam nguoi nhanh va kiem tra nhiet do"
        assert strip_accents(text) == expected

    def test_all_tone_variants(self):
        # a with all 6 tones
        assert strip_accents("aàáảãạ") == "aaaaaa"
        # o with all tones and modifiers (18 chars: bare o + 5 tones + 6 circumflex + 6 horn)
        assert strip_accents("oòóỏõọôồốổỗộơờớởỡợ") == "o" * 18

    def test_mixed_case_normalized(self):
        assert strip_accents("ĐẹP") == "dep"
        assert strip_accents("SỐ MùÔng") == "so muong"

    def test_no_vietnamese_chars(self):
        assert strip_accents("hello world") == "hello world"
        assert strip_accents("DHA, 120ml, 40°C") == "dha, 120ml, 40°c"

    def test_empty_string(self):
        assert strip_accents("") == ""

    def test_all_accent_map_keys_are_distinct(self):
        """Ensure every key in the map maps to something."""
        for ch, base in VIETNAMESE_ACCENT_MAP.items():
            assert len(ch) == 1, f"Key {ch!r} should be a single character"
            assert len(base) == 1, f"Base for {ch!r} should be a single character"

    def test_map_coverage(self):
        """All lowercase and uppercase accented chars should be in the map."""
        test_chars = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
        for ch in test_chars:
            assert ch in VIETNAMESE_ACCENT_MAP, f"Missing lowercase: {ch!r} (U+{ord(ch):04X})"

        test_chars_upper = "ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ"
        for ch in test_chars_upper:
            assert ch in VIETNAMESE_ACCENT_MAP, f"Missing uppercase: {ch!r} (U+{ord(ch):04X})"


class TestStripAccentsPreserveCase:
    def test_dd_lowercase(self):
        assert strip_accents_preserve_case("đ") == "d"

    def test_dd_uppercase(self):
        assert strip_accents_preserve_case("Đ") == "D"

    def test_mixed_case_preserved(self):
        assert strip_accents_preserve_case("Đường") == "Duong"

    def test_upper_phrase(self):
        assert strip_accents_preserve_case("RÓT NƯỚC") == "ROT NUOC"

    def test_lower_phrase(self):
        assert strip_accents_preserve_case("rót nước") == "rot nuoc"

    def test_mixed_sentence(self):
        text = "LÂM Người NHANH"
        expected = "LAM Nguoi NHANH"
        assert strip_accents_preserve_case(text) == expected

    def test_empty_string(self):
        assert strip_accents_preserve_case("") == ""


class TestToNoToneKey:
    def test_duong(self):
        assert to_no_tone_key("đường") == "duong"

    def test_dduong_uppercase(self):
        assert to_no_tone_key("ĐƯỜNG") == "duong"

    def test_so_hong(self):
        assert to_no_tone_key("Sổ hồng") == "so hong"

    def test_mixed_phrase(self):
        assert to_no_tone_key("RÓT NƯỚC VÀO") == "rot nuoc vao"

    def test_numbers_preserved(self):
        assert to_no_tone_key("120ml") == "120ml"

    def test_empty_string(self):
        assert to_no_tone_key("") == ""


class TestStripVietnameseAccents:
    def test_alias_equivalence(self):
        assert strip_vietnamese_accents("đường") == strip_accents("đường")
        assert strip_vietnamese_accents("RỐT") == strip_accents("RỐT")
