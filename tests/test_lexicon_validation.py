"""Tests for JSON lexicon validation."""

import json
from pathlib import Path
from typing import Any

from vn_corrector.common.validation import (
    validate_abbreviation_entry,
    validate_lexicon_file,
    validate_ocr_confusion_entry,
    validate_phrase_entry,
    validate_syllable_entry,
    validate_word_entry,
)

_RESOURCE_DIR = Path(__file__).parents[1] / "src" / "vn_corrector" / "resources" / "lexicons"


def _load_resource(filename: str) -> Any:
    with open(_RESOURCE_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


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

    def test_form_strips_to_wrong_base(self):
        """kiem with form kiện should fail — kiện strips to kien, not kiem."""
        entry = {
            "base": "kiem",
            "forms": ["kiểm", "kiện"],
            "freq": {"kiểm": 0.7, "kiện": 0.3},
        }
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("strips to" in e for e in result.errors)

    def test_form_strips_to_wrong_base_nhieu(self):
        """nhiet with form nhiều should fail — nhiều strips to nhieu, not nhiet."""
        entry = {
            "base": "nhiet",
            "forms": ["nhiệt", "nhiều"],
            "freq": {"nhiệt": 0.7, "nhiều": 0.3},
        }
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("strips to" in e for e in result.errors)

    def test_missing_freq_for_form(self):
        """If freq is provided, every form must have an entry."""
        entry = {
            "base": "muong",
            "forms": ["muỗng", "mường", "muống"],
            "freq": {"muỗng": 0.91, "mường": 0.05},
        }
        result = validate_syllable_entry(entry)
        assert not result.valid
        assert any("no frequency score" in e for e in result.errors)

    def test_all_forms_strip_correctly(self):
        """Every form must strip back to the declared base."""
        entry = {
            "base": "muong",
            "forms": ["muỗng", "mường", "muông"],
            "freq": {"muỗng": 0.91, "mường": 0.05, "muông": 0.02},
        }
        result = validate_syllable_entry(entry)
        assert result.valid


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

    def test_all_resource_files_valid(self):
        """Validate every built-in lexicon resource file."""
        resources: list[tuple[str, str]] = [
            ("syllables.vi.json", "syllable"),
            ("words.vi.json", "word"),
            ("units.vi.json", "unit"),
            ("abbreviations.vi.json", "abbreviation"),
            ("foreign_words.json", "foreign_words"),
            ("phrases.vi.json", "phrase"),
            ("ocr_confusions.vi.json", "ocr_confusion"),
        ]
        for filename, lexicon_type in resources:
            data = _load_resource(filename)
            result = validate_lexicon_file(data, lexicon_type)
            assert result.valid, f"{filename} validation failed: {result.errors}"


class TestValidatePhraseEntry:
    def test_valid_entry(self):
        entry = {"phrase": "số muỗng gạt ngang", "normalized": "so muong gat ngang", "n": 3}
        result = validate_phrase_entry(entry)
        assert result.valid

    def test_valid_entry_with_freq(self):
        entry = {
            "phrase": "số muỗng gạt ngang",
            "normalized": "so muong gat ngang",
            "n": 3,
            "freq": 0.9,
        }
        result = validate_phrase_entry(entry)
        assert result.valid

    def test_missing_phrase(self):
        entry = {"normalized": "so muong", "n": 2}
        result = validate_phrase_entry(entry)
        assert not result.valid
        assert any("phrase" in e for e in result.errors)

    def test_missing_n(self):
        entry = {"phrase": "số muỗng", "normalized": "so muong"}
        result = validate_phrase_entry(entry)
        assert not result.valid
        assert any("n" in e for e in result.errors)

    def test_invalid_n(self):
        entry = {"phrase": "test", "normalized": "test", "n": 0}
        result = validate_phrase_entry(entry)
        assert not result.valid

    def test_freq_out_of_range(self):
        entry = {"phrase": "test", "normalized": "test", "n": 2, "freq": 1.5}
        result = validate_phrase_entry(entry)
        assert not result.valid


class TestValidateOcrConfusionEntry:
    def test_valid_entry(self):
        entry = {"noisy": "mùông", "corrections": ["muỗng"]}
        result = validate_ocr_confusion_entry(entry)
        assert result.valid

    def test_valid_with_confidence(self):
        entry = {"noisy": "rốt", "corrections": ["rót"], "confidence": 0.8}
        result = validate_ocr_confusion_entry(entry)
        assert result.valid

    def test_missing_noisy(self):
        entry = {"corrections": ["muỗng"]}
        result = validate_ocr_confusion_entry(entry)
        assert not result.valid
        assert any("noisy" in e for e in result.errors)

    def test_empty_noisy(self):
        entry = {"noisy": "", "corrections": ["test"]}
        result = validate_ocr_confusion_entry(entry)
        assert not result.valid

    def test_missing_corrections(self):
        entry = {"noisy": "test"}
        result = validate_ocr_confusion_entry(entry)
        assert not result.valid

    def test_empty_corrections(self):
        entry = {"noisy": "test", "corrections": []}
        result = validate_ocr_confusion_entry(entry)
        assert not result.valid

    def test_confidence_out_of_range(self):
        entry = {"noisy": "test", "corrections": ["x"], "confidence": 1.5}
        result = validate_ocr_confusion_entry(entry)
        assert not result.valid

    def test_multiple_corrections(self):
        entry = {"noisy": "đẫn", "corrections": ["dẫn", "dần"]}
        result = validate_ocr_confusion_entry(entry)
        assert result.valid
