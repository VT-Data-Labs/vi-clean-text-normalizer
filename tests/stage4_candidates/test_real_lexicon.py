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
from vn_corrector.stage4_candidates.generator import merge_optional_max
from vn_corrector.stage4_candidates.sources.domain_specific import DomainSpecificSource
from vn_corrector.tokenizer import tokenize


@pytest.fixture(scope="session")
def real_lexicon():
    return load_default_lexicon(mode="hybrid")


@pytest.fixture(scope="session")
def gen(real_lexicon):
    return CandidateGenerator(real_lexicon)


# ---------------------------------------------------------------------------
#  M4.1 — Basic correction candidates
# ---------------------------------------------------------------------------


class TestBasicCorrection:
    """Prove that common Vietnamese OCR errors produce the expected
    correction candidates via the real bundled lexicon.
    """

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

    def test_long_generates_long_variant(self, gen: CandidateGenerator) -> None:
        candidates = gen.generate_token("long")
        texts = {c.text for c in candidates}
        assert "lòng" in texts, f"'lòng' not in candidates for 'long': {texts}"

    def test_long_survives_default_candidate_cap(self, gen: CandidateGenerator) -> None:
        config = CandidateGeneratorConfig(max_candidates_per_token=16)
        capped_gen = CandidateGenerator(gen._lexicon, config=config)
        candidates = capped_gen.generate_token("long")
        texts = {c.text for c in candidates}
        assert "lòng" in texts, f"'lòng' dropped from candidates at cap=16: {texts}"


# ---------------------------------------------------------------------------
#  replacement_token_count propagation (M4.5)
# ---------------------------------------------------------------------------


class TestReplacementTokenCount:
    """Abbreviation expansions with multiple tokens propagate ``replacement_token_count``."""

    def test_cc_has_replacement_token_count(self, gen: CandidateGenerator) -> None:
        """``cc -> chung cư`` has ``replacement_token_count=2``."""
        candidates = gen.generate_token("cc")
        cc = next((c for c in candidates if c.text == "chung cư"), None)
        assert cc is not None, "chung cư not found in candidates"
        assert cc.replacement_token_count >= 2, (
            f"Expected replacement_token_count >= 2, got {cc.replacement_token_count}"
        )

    def test_single_word_no_replacement_count(self, gen: CandidateGenerator) -> None:
        """Single-word candidates have ``replacement_token_count=1``."""
        candidates = gen.generate_token("mùông")
        for c in candidates:
            assert c.replacement_token_count == 1, (
                f"Candidate '{c.text}' has replacement_token_count={c.replacement_token_count}"
            )


# ---------------------------------------------------------------------------
#  Domain-specific source (M4.5)
# ---------------------------------------------------------------------------


class TestDomainSpecific:
    """Domain-specific source is registered and produces candidates when domain is set."""

    def test_domain_specific_source_registered(self, gen: CandidateGenerator) -> None:
        """DomainSpecificSource is registered when enable_domain_specific is True."""
        assert any(isinstance(s, DomainSpecificSource) for s in gen._sources)

    def test_domain_specific_disabled_when_config_off(self, gen: CandidateGenerator) -> None:
        """DomainSpecificSource is NOT registered when config disables it."""
        config = CandidateGeneratorConfig(cache_enabled=False, enable_domain_specific=False)
        gen_local = CandidateGenerator(gen._lexicon, config=config)
        assert not any(isinstance(s, DomainSpecificSource) for s in gen_local._sources)


# ---------------------------------------------------------------------------
#  Split candidate semantics — new field propagation
# ---------------------------------------------------------------------------


class TestCandidateSemantics:
    """Verify that source generators emit correct semantics for the new fields."""

    def test_word_lexicon_marks_known_word_without_syllable_freq(
        self, gen: CandidateGenerator
    ) -> None:
        """WordLexiconSource marks is_known_word=True. Merged candidates may also
        have syllable_freq if the same text was generated by SyllableMapSource.
        """
        candidates = gen.generate_token("muỗng")
        word_lex_cands = [c for c in candidates if CandidateSource.WORD_LEXICON in c.sources]
        for c in word_lex_cands:
            assert c.is_known_word, f"Word-lexicon candidate '{c.text}' not marked known"

    def test_syllable_map_preserves_frequency(self, gen: CandidateGenerator) -> None:
        """SyllableMapSource sets syllable_freq, and 'cấp' outranks 'cáp'."""
        candidates = gen.generate_token("cap")
        by_text = {c.text: c for c in candidates}
        if "cấp" in by_text and "cáp" in by_text:
            assert by_text["cấp"].syllable_freq is not None
            assert by_text["cáp"].syllable_freq is not None
            assert by_text["cấp"].syllable_freq >= by_text["cáp"].syllable_freq

    def test_known_word_does_not_overwrite_syllable_frequency(
        self, gen: CandidateGenerator
    ) -> None:
        """After merge, a candidate can be both is_known_word and have syllable_freq."""
        candidates = gen.generate_token("cap")
        by_text = {c.text: c for c in candidates}
        if "cấp" in by_text:
            c = by_text["cấp"]
            # If WordLexiconSource contributed 'cấp', it should be known
            known = CandidateSource.WORD_LEXICON in c.sources
            assert c.is_known_word == known, (
                f"'cấp': is_known_word={c.is_known_word} but sources={c.sources}"
            )
            # Syllable_freq may or may not be set depending on syllable_map
            if c.syllable_freq is not None:
                assert c.syllable_freq > 0, f"'cấp' has syllable_freq={c.syllable_freq}"

    def test_unicode_text_is_not_ranking_tiebreaker(self, gen: CandidateGenerator) -> None:
        """candidate.text must not be a ranking tiebreaker; 'cấp' should appear early."""
        candidates = gen.generate_token("cap")
        texts = [c.text for c in candidates]
        if "cấp" in texts:
            assert texts.index("cấp") <= 8, (
                f"'cấp' ranked too low (position {texts.index('cấp')}): {texts[:10]}"
            )


class TestMergeOptionalMax:
    """Unit tests for the merge_optional_max helper."""

    def test_both_none(self) -> None:
        assert merge_optional_max(None, None) is None

    def test_old_none(self) -> None:
        assert merge_optional_max(None, 5.0) == 5.0

    def test_new_none(self) -> None:
        assert merge_optional_max(5.0, None) == 5.0

    def test_both_values(self) -> None:
        assert merge_optional_max(3.0, 5.0) == 5.0
        assert merge_optional_max(5.0, 3.0) == 5.0
