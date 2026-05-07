"""Tests for all Stage-2 lexicon builders."""

from vn_corrector.common.enums import LexiconKind, LexiconSource
from vn_corrector.lexicon.types import (
    AbbreviationEntry,
    LexiconEntry,
    OcrConfusionEntry,
    PhraseEntry,
)
from vn_corrector.stage2_lexicon.builders import (
    AbbreviationBuilder,
    ConfusionBuilder,
    PhraseBuilder,
    SyllableBuilder,
    WordBuilder,
)
from vn_corrector.stage2_lexicon.core.types import BuilderInput

# ======================================================================
# SyllableBuilder
# ======================================================================


class TestSyllableBuilder:
    def setup_method(self) -> None:
        self.builder = SyllableBuilder()

    def test_build_single_entry(self):
        data = [{"base": "muong", "forms": ["muỗng", "mường"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 2
        assert output.entries[0].surface in ("muỗng", "mường")
        assert output.entries[0].no_tone == "muong"
        assert output.entries[0].kind == LexiconKind.SYLLABLE

    def test_build_with_freq(self):
        data = [
            {"base": "muong", "forms": ["muỗng", "mường"], "freq": {"muỗng": 0.9, "mường": 0.1}},
        ]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 2
        freq_map = {e.surface: e.score.confidence for e in output.entries}
        assert freq_map["muỗng"] == 0.9
        assert freq_map["mường"] == 0.1

    def test_build_empty_data(self):
        output = self.builder.build(BuilderInput(name="test", data=[]))
        assert len(output.entries) == 0

    def test_build_invalid_data_raises(self):
        import pytest

        with pytest.raises(TypeError):
            self.builder.build(BuilderInput(name="test", data="not a list"))

    def test_validate_output_valid(self):
        data = [{"base": "muong", "forms": ["muỗng"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert errors == []

    def test_validate_output_empty_surface(self):
        entry = LexiconEntry(
            entry_id="test/",
            surface="",
            normalized="",
            no_tone="muong",
            kind=LexiconKind.SYLLABLE,
        )
        errors = self.builder.validate_output([entry])
        assert len(errors) > 0

    def test_provenance_source(self):
        data = [{"base": "muong", "forms": ["muỗng"]}]
        output = self.builder.build(
            BuilderInput(name="test", data=data, source=LexiconSource.CORPUS, version="1.0")
        )
        assert output.entries[0].provenance.source == LexiconSource.CORPUS
        assert output.entries[0].provenance.version == "1.0"


# ======================================================================
# WordBuilder
# ======================================================================


class TestWordBuilder:
    def setup_method(self) -> None:
        self.builder = WordBuilder()

    def test_build_single_entry(self):
        data = [{"surface": "số muỗng", "type": "common_word", "freq": 0.9}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        assert output.entries[0].surface == "số muỗng"
        assert output.entries[0].no_tone == "so muong"
        assert output.entries[0].kind == LexiconKind.WORD

    def test_build_unit(self):
        data = [{"surface": "kg", "type": "unit_word", "freq": 1.0}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        assert output.entries[0].kind == LexiconKind.UNIT

    def test_build_with_domain(self):
        data = [{"surface": "DHA", "type": "chemical", "domain": "milk_formula"}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        assert output.entries[0].domain == "milk_formula"
        assert output.entries[0].kind == LexiconKind.DOMAIN_TERM

    def test_build_empty(self):
        output = self.builder.build(BuilderInput(name="test", data=[]))
        assert len(output.entries) == 0

    def test_validate_valid(self):
        data = [{"surface": "test", "freq": 0.5}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert errors == []

    def test_validate_negative_freq(self):
        data = [{"surface": "test", "freq": -0.1}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert len(errors) > 0


# ======================================================================
# PhraseBuilder
# ======================================================================


class TestPhraseBuilder:
    def setup_method(self) -> None:
        self.builder = PhraseBuilder()

    def test_build_single_entry(self):
        data = [{"phrase": "số muỗng gạt ngang", "n": 3, "freq": 0.9}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        entry = output.entries[0]
        assert isinstance(entry, PhraseEntry)
        assert entry.phrase == "số muỗng gạt ngang"
        assert entry.n == 3
        assert entry.score.confidence == 0.9

    def test_build_with_domain(self):
        data = [{"phrase": "làm nguội nhanh", "n": 3, "domain": "product_instruction"}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert output.entries[0].domain == "product_instruction"

    def test_build_empty(self):
        output = self.builder.build(BuilderInput(name="test", data=[]))
        assert len(output.entries) == 0

    def test_validate_valid(self):
        data = [{"phrase": "test phrase", "n": 2}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert errors == []

    def test_validate_invalid_n(self):
        data = [{"phrase": "test", "n": 0}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert len(errors) > 0


# ======================================================================
# ConfusionBuilder
# ======================================================================


class TestConfusionBuilder:
    def setup_method(self) -> None:
        self.builder = ConfusionBuilder()

    def test_build_single_entry(self):
        data = [{"noisy": "mùông", "corrections": ["muỗng"], "confidence": 0.8}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        entry = output.entries[0]
        assert isinstance(entry, OcrConfusionEntry)
        assert entry.noisy == "mùông"
        assert entry.corrections == ("muỗng",)
        assert entry.score.confidence == 0.8

    def test_build_multiple_corrections(self):
        data = [{"noisy": "đẫn", "corrections": ["dẫn", "dần"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        assert output.entries[0].corrections == ("dẫn", "dần")

    def test_build_empty(self):
        output = self.builder.build(BuilderInput(name="test", data=[]))
        assert len(output.entries) == 0

    def test_validate_valid(self):
        data = [{"noisy": "test", "corrections": ["fix"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert errors == []

    def test_empty_corrections_skipped(self):
        data = [{"noisy": "test", "corrections": []}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        # Empty corrections are skipped, producing zero entries
        assert len(output.entries) == 0


# ======================================================================
# AbbreviationBuilder
# ======================================================================


class TestAbbreviationBuilder:
    def setup_method(self) -> None:
        self.builder = AbbreviationBuilder()

    def test_build_single_entry(self):
        data = [{"abbreviation": "2pn", "expansions": ["2 phòng ngủ"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert len(output.entries) == 1
        entry = output.entries[0]
        assert isinstance(entry, AbbreviationEntry)
        assert entry.surface == "2pn"
        assert entry.expansions == ("2 phòng ngủ",)

    def test_build_multiple_expansions(self):
        data = [{"abbreviation": "dt", "expansions": ["diện tích", "đường trước"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert output.entries[0].expansions == ("diện tích", "đường trước")
        assert output.entries[0].ambiguous

    def test_build_single_expansion_not_ambiguous(self):
        data = [{"abbreviation": "q.", "expansions": ["quận"], "ambiguous": False}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        assert not output.entries[0].ambiguous

    def test_build_empty(self):
        output = self.builder.build(BuilderInput(name="test", data=[]))
        assert len(output.entries) == 0

    def test_validate_valid(self):
        data = [{"abbreviation": "test", "expansions": ["expansion"]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert errors == []

    def test_validate_empty_expansion_string(self):
        data = [{"abbreviation": "test", "expansions": [""]}]
        output = self.builder.build(BuilderInput(name="test", data=data))
        errors = self.builder.validate_output(list(output.entries))
        assert len(errors) > 0
