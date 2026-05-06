"""Acceptance tests using the real bundled JSON lexicon.

These tests prove the M4 pipeline actually produces useful
Vietnamese correction candidates with real data.
"""

from __future__ import annotations

import pytest

from vn_corrector.stage2_lexicon import load_default_lexicon
from vn_corrector.stage4_candidates import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    CandidateSource,
)
from vn_corrector.tokenizer import tokenize


@pytest.fixture(scope="session")
def real_lexicon():
    return load_default_lexicon(mode="json")


@pytest.fixture(scope="session")
def gen(real_lexicon):
    return CandidateGenerator(real_lexicon)


# ---------------------------------------------------------------------------
#  M4.1 — Basic correction candidates
# ---------------------------------------------------------------------------


class TestBasicCorrection:
    """Prove that common Vietnamese OCR errors produce the expected
    correction candidates via the real bundled lexicon."""

    def test_muong_contains_muong(self, gen: CandidateGenerator) -> None:
        """OCR error ``mùông`` should yield ``muỗng``."""
        texts = {c.text for c in gen.generate_token("mùông")}
        assert "muỗng" in texts

    def test_muong_has_ocr_and_syllable_sources(self, gen: CandidateGenerator) -> None:
        """``muỗng`` candidate should have OCR+SYLLABLE+ORIGINAL sources."""
        candidates = gen.generate_token("mùông")
        muong = next(c for c in candidates if c.text == "muỗng")
        assert CandidateSource.OCR_CONFUSION in muong.sources
        assert CandidateSource.SYLLABLE_MAP in muong.sources

    def test_dan_generates_dan_variants(self, gen: CandidateGenerator) -> None:
        """No-tone ``đẫn`` should yield ``dẫn`` and ``dần``."""
        texts = {c.text for c in gen.generate_token("đẫn")}
        assert "dẫn" in texts
        assert "dần" in texts

    def test_original_always_present(self, gen: CandidateGenerator) -> None:
        """Original token text is always among the candidates."""
        for raw in ("mùông", "đẫn", "muỗng", "hello"):
            texts = {c.text for c in gen.generate_token(raw)}
            assert raw in texts


# ---------------------------------------------------------------------------
#  Protected / special tokens
# ---------------------------------------------------------------------------


class TestProtectedTokens:
    """Tokens matching protection rules should produce identity only."""

    def test_phone_number(self, gen: CandidateGenerator) -> None:
        texts = {c.text for c in gen.generate_token("0978123456")}
        assert texts == {"0978123456"}

    def test_code_with_numbers(self, gen: CandidateGenerator) -> None:
        texts = {c.text for c in gen.generate_token("HA02")}
        assert texts == {"HA02"}

    def test_number_token(self, gen: CandidateGenerator) -> None:
        texts = {c.text for c in gen.generate_token("123")}
        assert texts == {"123"}


# ---------------------------------------------------------------------------
#  Abbreviation expansion
# ---------------------------------------------------------------------------


class TestAbbreviation:
    """Known abbreviations should expand to full forms."""

    def test_cc_expands(self, gen: CandidateGenerator) -> None:
        texts = {c.text for c in gen.generate_token("cc")}
        assert "chung cư" in texts

    def test_abbreviation_has_correct_source(self, gen: CandidateGenerator) -> None:
        candidates = gen.generate_token("cc")
        cc = next(c for c in candidates if c.text == "chung cư")
        assert CandidateSource.ABBREVIATION in cc.sources


# ---------------------------------------------------------------------------
#  Document-level generation
# ---------------------------------------------------------------------------


class TestDocumentGeneration:
    """Full document pass produces reasonable results."""

    def test_simple_document(self, gen: CandidateGenerator) -> None:
        tokens = tokenize("số mùông")
        doc = gen.generate_document(tokens)
        assert doc.stats.total_tokens >= 2
        assert doc.stats.total_candidates > 0

    def test_every_token_has_candidates(self, gen: CandidateGenerator) -> None:
        tokens = tokenize("người đẫn đường")
        doc = gen.generate_document(tokens)
        for tc in doc.token_candidates:
            assert len(tc.candidates) >= 1, f"Token '{tc.token_text}' has no candidates"

    def test_protected_token_identity(self, gen: CandidateGenerator) -> None:
        tokens = tokenize("số 123 mùông")
        doc = gen.generate_document(tokens)
        for tc in doc.token_candidates:
            if tc.token_text == "123":
                assert len(tc.candidates) == 1
                assert tc.candidates[0].is_original


# ---------------------------------------------------------------------------
#  Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions with the real lexicon."""

    def test_empty_string(self, gen: CandidateGenerator) -> None:
        candidates = gen.generate_token("")
        assert len(candidates) == 0

    def test_single_character(self, gen: CandidateGenerator) -> None:
        candidates = gen.generate_token("a")
        assert len(candidates) >= 1

    def test_known_word_does_not_disappear(self, gen: CandidateGenerator) -> None:
        """A correctly-spelled word should keep itself."""
        candidates = gen.generate_token("muỗng")
        texts = {c.text for c in candidates}
        assert "muỗng" in texts

    def test_max_candidates_respected(self, gen: CandidateGenerator) -> None:
        config = CandidateGeneratorConfig(max_candidates_per_token=3)
        small_gen = CandidateGenerator(gen._lexicon, config=config)
        candidates = small_gen.generate_token("mùông")
        assert len(candidates) <= 3
