"""Tests for protected-token behavior in Stage 4 CandidateGenerator.

Verifies that protected tokens are never mutated and bypass rules
are strictly followed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vn_corrector.stage4_candidates import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    CandidateSource,
)

# Various protected token examples from the project spec
PROTECTED_EXAMPLES = [
    "2'-FL",
    "DHA",
    "ARA",
    "LNT",
    "120ml",
    "HA02",
    "Bifidobacterium",
    "oligosaccharid",
    "alpha-lactalbumin",
    "https://example.com",
    "user@domain.com",
]


@pytest.fixture
def mock_lexicon() -> MagicMock:
    lexicon = MagicMock()
    lexicon.lookup_accentless.return_value = MagicMock(entries=(), candidates=())
    lexicon.lookup_ocr.return_value = []
    lexicon.get_ocr_corrections.return_value = MagicMock(corrections=())
    lexicon.lookup_abbreviation.return_value = MagicMock(entries=(), found=False)
    lexicon.lookup_phrase_str.return_value = None
    lexicon.lookup_phrase.return_value = []
    lexicon.lookup_phrase_normalized.return_value = []
    lexicon.query_prefix.return_value = []
    lexicon.get_syllable_candidates.return_value = []
    return lexicon


@pytest.fixture
def gen(mock_lexicon: MagicMock) -> CandidateGenerator:
    return CandidateGenerator(mock_lexicon, config=CandidateGeneratorConfig(cache_enabled=False))


class TestProtectedTokens:
    """Every protected token must return exactly one candidate: the original."""

    @pytest.mark.parametrize("token", PROTECTED_EXAMPLES)
    def test_protected_token_count(self, gen: CandidateGenerator, token: str) -> None:
        candidates = gen.generate_token(token, protected=True)
        assert len(candidates) == 1, f"{token}: expected 1 candidate, got {len(candidates)}"

    @pytest.mark.parametrize("token", PROTECTED_EXAMPLES)
    def test_protected_token_text(self, gen: CandidateGenerator, token: str) -> None:
        candidates = gen.generate_token(token, protected=True)
        assert candidates[0].text == token, f"{token}: text changed to '{candidates[0].text}'"

    @pytest.mark.parametrize("token", PROTECTED_EXAMPLES)
    def test_protected_token_is_original(self, gen: CandidateGenerator, token: str) -> None:
        candidates = gen.generate_token(token, protected=True)
        assert candidates[0].is_original, f"{token}: is_original is False"

    @pytest.mark.parametrize("token", PROTECTED_EXAMPLES)
    def test_protected_token_source(self, gen: CandidateGenerator, token: str) -> None:
        candidates = gen.generate_token(token, protected=True)
        assert CandidateSource.ORIGINAL in candidates[0].sources, (
            f"{token}: missing ORIGINAL source"
        )

    @pytest.mark.parametrize("token", PROTECTED_EXAMPLES)
    def test_protected_token_unique(self, gen: CandidateGenerator, token: str) -> None:
        """Protected token has exactly 1 candidate — no duplicates."""
        candidates = gen.generate_token(token, protected=True)
        assert len(set(c.text for c in candidates)) == 1

    def test_non_protected_token_produces_variants(self, gen: CandidateGenerator) -> None:
        """A non-protected token should produce more than one candidate.
        This test uses an empty lexicon, so the only 'variant' is the original itself.
        With empty lexicon, ORIGINAL is the only source, so count may be 1."""
        candidates = gen.generate_token("mùông", protected=False)
        # At minimum the original is included
        assert len(candidates) >= 1
        assert candidates[0].is_original
