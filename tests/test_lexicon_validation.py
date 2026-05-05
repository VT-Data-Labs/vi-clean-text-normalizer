"""Tests for JSON lexicon validation."""

from vn_corrector.common.validation import (
    validate_abbreviation_entry,
    validate_lexicon_file,
    validate_syllable_entry,
    validate_word_entry,
)


class TestValidateSyllableEntry:
    def test_valid_entry(self):
        entry = {
            "base": "muong",
            "forms": ["muỗng", "mường"],
            "freq": {"muỗng": 0.91, "mường": 0.05},
        }
        result = validate_syllable_entry(entry)
        assert result.valid

    def test_missing_base(self):
        entry = {"forms": ["muỗng"]}
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("base" in e for e in result.errors)

    def test_empty_base(self):
        entry = {"base": "", "forms": ["muỗng"]}
        result = validate_syllable_entry(entry)
        assert not result.valid

    def test_missing_forms(self):
        entry = {"base": "muong"}
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("forms" in e for e in result.errors)

    def test_empty_forms(self):
        entry = {"base": "muong", "forms": []}
        result = validate_syllable_entry(entry)
        assert not result.valid

    def test_freq_out_of_range(self):
        entry = {"base": "muong", "forms": ["muỗng"], "freq": {"muỗng": 1.5}}
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("between 0 and 1" in e for e in result.errors)

    def test_duplicate_forms(self):
        entry = {"base": "muong", "forms": ["muỗng", "muỗng"]}
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("Duplicate" in e for e in result.errors)


class TestValidateWordEntry:
    def test_valid_entry(self):
        entry = {
            "surface": "số muỗng",
            "normalized": "so muong",
            "type": "common_word",
            "freq": 0.9,
        }
        result = validate_word_entry(entry)
        assert result.valid

    def test_valid_entry_no_freq(self):
        entry = {"surface": "số muỗng", "normalized": "so muong"}
        result = validate_word_entry(entry)
        assert result.valid

    def test_missing_surface(self):
        entry = {"normalized": "so muong"}
        result = validate_word_entry(entry)
        assert not result.valid
        assert any("surface" in e for e in result.errors)

    def test_missing_normalized(self):
        entry = {"surface": "số muỗng"}
        result = validate_word_entry(entry)
        assert not result.valid

    def test_empty_surface(self):
        entry = {"surface": "", "normalized": "so muong"}
        result = validate_word_entry(entry)
        assert not result.valid

    def test_freq_out_of_range(self):
        entry = {"surface": "test", "normalized": "test", "freq": 1.5}
        result = validate_word_entry(entry)
        assert not result.valid

    def test_negative_freq(self):
        entry = {"surface": "test", "normalized": "test", "freq": -0.1}
        result = validate_word_entry(entry)
        assert not result.valid


class TestValidateAbbreviationEntry:
    def test_valid_entry(self):
        entry = {"abbreviation": "2pn", "expansions": ["2 phòng ngủ"]}
        result = validate_abbreviation_entry(entry)
        assert result.valid

    def test_missing_abbreviation(self):
        entry = {"expansions": ["2 phòng ngủ"]}
        result = validate_abbreviation_entry(entry)
        assert not result.valid
        assert any("abbreviation" in e for e in result.errors)

    def test_empty_abbreviation(self):
        entry = {"abbreviation": "", "expansions": ["2 phòng ngủ"]}
        result = validate_abbreviation_entry(entry)
        assert not result.valid

    def test_missing_expansions(self):
        entry = {"abbreviation": "2pn"}
        result = validate_abbreviation_entry(entry)
        assert not result.valid

    def test_empty_expansions(self):
        entry = {"abbreviation": "2pn", "expansions": []}
        result = validate_abbreviation_entry(entry)
        assert not result.valid
        assert any("non-empty" in e for e in result.errors)

    def test_expansion_empty_string(self):
        entry = {"abbreviation": "2pn", "expansions": [""]}
        result = validate_abbreviation_entry(entry)
        assert not result.valid

    def test_multiple_expansions(self):
        entry = {"abbreviation": "dt", "expansions": ["diện tích", "đường trước"]}
        result = validate_abbreviation_entry(entry)
        assert result.valid


class TestValidateLexiconFile:
    def test_valid_syllable_file(self):
        data = [
            {"base": "muong", "forms": ["muỗng", "mường"]},
            {"base": "duong", "forms": ["đường", "dương"]},
        ]
        result = validate_lexicon_file(data, "syllable")
        assert result.valid

    def test_valid_word_file(self):
        data = [
            {"surface": "số muỗng", "normalized": "so muong"},
            {"surface": "hướng dẫn", "normalized": "huong dan"},
        ]
        result = validate_lexicon_file(data, "word")
        assert result.valid

    def test_duplicate_normalized_in_words(self):
        data = [
            {"surface": "số", "normalized": "so"},
            {"surface": "sổ", "normalized": "so"},
        ]
        result = validate_lexicon_file(data, "word")
        assert not result.valid
        assert any("Duplicate" in e for e in result.errors)

    def test_valid_abbreviation_file(self):
        data = [
            {"abbreviation": "2pn", "expansions": ["2 phòng ngủ"]},
            {"abbreviation": "dt", "expansions": ["diện tích"]},
        ]
        result = validate_lexicon_file(data, "abbreviation")
        assert result.valid

    def test_valid_foreign_words(self):
        data = ["DHA", "ARA", "Lactose"]
        result = validate_lexicon_file(data, "foreign_words")
        assert result.valid

    def test_invalid_foreign_words(self):
        data = ["DHA", "", "Lactose"]
        result = validate_lexicon_file(data, "foreign_words")
        assert not result.valid

    def test_data_is_not_list(self):
        result = validate_lexicon_file({"key": "value"}, "word")
        assert not result.valid
        assert any("must be a list" in e for e in result.errors)

    def test_unknown_type(self):
        result = validate_lexicon_file([], "unknown_type")
        assert not result.valid

    def test_entry_not_dict(self):
        data = ["not a dict"]
        result = validate_lexicon_file(data, "word")
        assert not result.valid
