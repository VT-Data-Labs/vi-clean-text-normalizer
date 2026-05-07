"""Tests for the pipeline TextCorrector and correct_text()."""

from __future__ import annotations

import pytest

from vn_corrector.common.correction import CorrectionResult
from vn_corrector.pipeline import TextCorrector, correct_text
from vn_corrector.pipeline.config import PipelineConfig
from vn_corrector.pipeline.errors import PipelineInputTooLargeError


class TestCorrectText:
    """End-to-end tests for the convenience ``correct_text()`` function."""

    def test_runs_real_pipeline(self) -> None:
        result = correct_text("neu do am vua du")
        assert isinstance(result, CorrectionResult)
        assert isinstance(result.corrected_text, str)
        assert isinstance(result.changes, tuple)

    def test_unknown_text_preserved(self) -> None:
        result = correct_text("zzqxxabc")
        assert result.corrected_text == "zzqxxabc"
        assert len(result.changes) == 0

    def test_empty_string(self) -> None:
        result = correct_text("")
        assert result.corrected_text == ""
        assert result.confidence == 1.0

    def test_whitespace_only(self) -> None:
        result = correct_text("   ")
        assert result.corrected_text is not None

    def test_result_structure(self) -> None:
        result = correct_text("xin chao")
        assert hasattr(result, "original_text")
        assert hasattr(result, "corrected_text")
        assert hasattr(result, "confidence")
        assert hasattr(result, "changes")
        assert hasattr(result, "flags")
        assert hasattr(result, "metadata")
        assert 0.0 <= result.confidence <= 1.0

    def test_metadata_present(self) -> None:
        result = correct_text("xin chao")
        assert "pipeline_version" in result.metadata
        assert result.metadata["pipeline_version"] == "m6.5"

    def test_punctuation_preserved(self) -> None:
        result = correct_text("neu do am vua du, ok?")
        assert ", ok?" in result.corrected_text

    def test_phone_number_preserved(self) -> None:
        result = correct_text("lh 0903.123.456 neu do am vua du")
        assert "0903.123.456" in result.corrected_text

    def test_low_confidence_keeps_original(self) -> None:
        config = PipelineConfig(min_accept_confidence=0.99, min_margin=0.50)
        result = correct_text("neu do am vua du", config=config)
        assert result.corrected_text is not None

    def test_input_too_large(self) -> None:
        config = PipelineConfig(max_input_chars=10)
        corrector = TextCorrector(config=config)
        with pytest.raises(PipelineInputTooLargeError):
            corrector.correct("x" * 11)

    def test_fail_closed_on_error(self) -> None:
        config = PipelineConfig(fail_closed=True, max_input_chars=5)
        corrector = TextCorrector(config=config)
        result = corrector.correct("valid")
        assert isinstance(result, CorrectionResult)
        assert result.corrected_text is not None

    def test_non_string_input(self) -> None:
        with pytest.raises(TypeError):
            correct_text(123)  # type: ignore[arg-type]

    def test_domain_passed_through(self) -> None:
        result = correct_text("neu do am vua du", domain="general")
        assert isinstance(result, CorrectionResult)


class TestTextCorrector:
    """Tests for the reusable ``TextCorrector`` class."""

    def test_reusable(self) -> None:
        corrector = TextCorrector()
        r1 = corrector.correct("xin chao")
        r2 = corrector.correct("tam biet")
        assert isinstance(r1, CorrectionResult)
        assert isinstance(r2, CorrectionResult)

    def test_config_passed_through(self) -> None:
        config = PipelineConfig(normalize=False)
        corrector = TextCorrector(config=config)
        result = corrector.correct("xin chao")
        assert isinstance(result, CorrectionResult)

    def test_multiple_calls_same_instance(self) -> None:
        corrector = TextCorrector()
        results = [corrector.correct("xin chao") for _ in range(5)]
        for r in results:
            assert isinstance(r, CorrectionResult)
