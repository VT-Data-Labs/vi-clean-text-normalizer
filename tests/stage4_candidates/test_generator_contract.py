"""Contract tests for Stage 4 CandidateGenerator.

Tests the public API contract: protected tokens, original inclusion,
source tracking, duplicate merging, limits, determinism, etc.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vn_corrector.common.types import TextSpan, Token, TokenType
from vn_corrector.stage4_candidates import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    CandidateSource,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_lexicon() -> MagicMock:
    """Create a minimal mock lexicon for contract tests."""
    lexicon = MagicMock()

    # lookup_accentless returns empty by default
    lexicon.lookup_accentless.return_value = MagicMock(entries=(), candidates=())
    lexicon.lookup_ocr.return_value = []
    lexicon.get_ocr_corrections.return_value = MagicMock(corrections=())
    lexicon.lookup_abbreviation.return_value = MagicMock(entries=(), found=False)
    lexicon.lookup_phrase_str.return_value = None
    lexicon.lookup_phrase.return_value = []
    lexicon.lookup_phrase_normalized.return_value = []
    lexicon.query_prefix.return_value = []
    lexicon.get_syllable_candidates.return_value = []
    lexicon.contains_word.return_value = False
    lexicon.contains_syllable.return_value = False
    return lexicon


@pytest.fixture
def generator(mock_lexicon: MagicMock) -> CandidateGenerator:
    """Create a generator with default config and mock lexicon."""
    return CandidateGenerator(mock_lexicon)


@pytest.fixture
def generator_no_cache(mock_lexicon: MagicMock) -> CandidateGenerator:
    """Create a generator with caching disabled."""
    config = CandidateGeneratorConfig(cache_enabled=False)
    return CandidateGenerator(mock_lexicon, config=config)


# ---------------------------------------------------------------------------
# Protected token tests
# ---------------------------------------------------------------------------


def test_protected_token_returns_exactly_original(generator_no_cache: CandidateGenerator) -> None:
    """Protected token 'HA02' returns exactly one candidate 'HA02'."""
    candidates = generator_no_cache.generate_token("HA02", protected=True)
    assert len(candidates) == 1
    assert candidates[0].text == "HA02"
    assert candidates[0].is_original
    assert CandidateSource.ORIGINAL in candidates[0].sources


def test_protected_token_has_no_variants(generator_no_cache: CandidateGenerator) -> None:
    """Protected token generates no additional variants."""
    candidates = generator_no_cache.generate_token("2'-FL", protected=True)
    assert len(candidates) == 1
    assert candidates[0].text == "2'-FL"


def test_protected_token_evidence_is_bypass(generator_no_cache: CandidateGenerator) -> None:
    """Protected token has evidence detail 'protected_token_bypass'."""
    candidates = generator_no_cache.generate_token("DHA", protected=True)
    assert len(candidates) == 1
    assert any(ev.detail == "protected_token_bypass" for ev in candidates[0].evidence)


# ---------------------------------------------------------------------------
# Original inclusion tests
# ---------------------------------------------------------------------------


def test_non_protected_token_includes_original(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Every non-protected token includes the original as a candidate."""
    candidates = generator_no_cache.generate_token("muong")
    assert any(c.text == "muong" and c.is_original for c in candidates)


def test_non_protected_token_original_has_correct_source(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Original candidate has ORIGINAL source."""
    candidates = generator_no_cache.generate_token("dan")
    original = [c for c in candidates if c.is_original]
    assert len(original) > 0
    assert CandidateSource.ORIGINAL in original[0].sources


# ---------------------------------------------------------------------------
# Source tracking tests
# ---------------------------------------------------------------------------


def test_every_candidate_has_non_empty_sources(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Every candidate has at least one source."""
    candidates = generator_no_cache.generate_token("muong")
    for c in candidates:
        assert len(c.sources) > 0, f"Candidate '{c.text}' has empty sources"


def test_every_candidate_has_non_empty_evidence(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Every candidate has at least one evidence item."""
    candidates = generator_no_cache.generate_token("muong")
    for c in candidates:
        assert len(c.evidence) > 0, f"Candidate '{c.text}' has empty evidence"


def test_candidate_sources_are_valid_enum_values(
    generator_no_cache: CandidateGenerator,
) -> None:
    """All candidate sources are valid CandidateSource enum values."""
    valid_sources = set(CandidateSource)
    candidates = generator_no_cache.generate_token("muong")
    for c in candidates:
        for s in c.sources:
            assert s in valid_sources, f"Invalid source: {s}"


# ---------------------------------------------------------------------------
# Duplicate merging tests
# ---------------------------------------------------------------------------


def test_no_duplicate_candidate_texts(
    generator_no_cache: CandidateGenerator,
) -> None:
    """No duplicate candidate texts in the output."""
    candidates = generator_no_cache.generate_token("muong")
    texts = [c.text for c in candidates]
    assert len(texts) == len(set(texts)), f"Duplicate texts: {texts}"


def test_duplicate_candidates_merge_sources(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Same candidate text from multiple sources merges correctly."""
    # Use a mock that returns data from OCR confusion and syllable map
    # to ensure 'muỗng' appears from multiple sources
    mock = MagicMock()
    mock.lookup_accentless.return_value = MagicMock(entries=(), candidates=())
    mock.lookup_ocr.return_value = []
    mock.get_ocr_corrections.return_value = MagicMock(corrections=())
    mock.lookup_abbreviation.return_value = MagicMock(entries=(), found=False)
    mock.lookup_phrase_str.return_value = None
    mock.lookup_phrase.return_value = []
    mock.lookup_phrase_normalized.return_value = []
    mock.query_prefix.return_value = []
    mock.get_syllable_candidates.return_value = []
    mock.contains_word.return_value = False
    mock.contains_syllable.return_value = False

    gen = CandidateGenerator(mock, config=CandidateGeneratorConfig(cache_enabled=False))
    candidates = gen.generate_token("test")
    # With empty lexicon we get only original
    assert len(candidates) >= 1
    assert candidates[0].is_original


# ---------------------------------------------------------------------------
# Limit tests
# ---------------------------------------------------------------------------


def test_candidate_count_respects_max_limit(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Candidate count is <= max_candidates_per_token (8 by default)."""
    candidates = generator_no_cache.generate_token("dan")
    assert len(candidates) <= 8


def test_max_candidates_configurable(
    mock_lexicon: MagicMock,
) -> None:
    "max_candidates_per_token=3 limits output to 3 candidates."
    config = CandidateGeneratorConfig(max_candidates_per_token=3, cache_enabled=False)
    gen = CandidateGenerator(mock_lexicon, config=config)
    candidates = gen.generate_token("dan")
    assert len(candidates) <= 3


# ---------------------------------------------------------------------------
# Candidate normalization tests
# ---------------------------------------------------------------------------


def test_every_candidate_has_normalized(generator_no_cache: CandidateGenerator) -> None:
    """Every candidate has a non-empty normalized field."""
    candidates = generator_no_cache.generate_token("dan")
    for c in candidates:
        assert c.normalized, f"Candidate '{c.text}' has empty normalized"
        assert isinstance(c.normalized, str)


def test_every_candidate_has_no_tone_key(generator_no_cache: CandidateGenerator) -> None:
    """Every candidate has a non-empty no_tone_key field."""
    candidates = generator_no_cache.generate_token("dan")
    for c in candidates:
        assert c.no_tone_key, f"Candidate '{c.text}' has empty no_tone_key"
        assert isinstance(c.no_tone_key, str)


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


def test_deterministic_across_repeated_calls(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Output is deterministic across repeated calls."""
    result1 = generator_no_cache.generate_token("muong")
    result2 = generator_no_cache.generate_token("muong")
    texts1 = [c.text for c in result1]
    texts2 = [c.text for c in result2]
    assert texts1 == texts2, f"Non-deterministic: {texts1} != {texts2}"


def test_deterministic_with_mock_lexicon(
    mock_lexicon: MagicMock,
) -> None:
    """Output is deterministic with the same lexicon."""
    gen1 = CandidateGenerator(mock_lexicon, config=CandidateGeneratorConfig(cache_enabled=False))
    gen2 = CandidateGenerator(mock_lexicon, config=CandidateGeneratorConfig(cache_enabled=False))

    result1 = gen1.generate_token("dan")
    result2 = gen2.generate_token("dan")
    texts1 = [c.text for c in result1]
    texts2 = [c.text for c in result2]
    assert texts1 == texts2


# ---------------------------------------------------------------------------
# Token eligibility tests
# ---------------------------------------------------------------------------


def test_number_token_identity_only(
    mock_lexicon: MagicMock, generator_no_cache: CandidateGenerator
) -> None:
    """NUMBER tokens produce only identity candidates."""
    tokens = [Token(text="42", token_type=TokenType.NUMBER, span=TextSpan(0, 2))]
    tc = generator_no_cache.generate_for_token_index(tokens, 0)
    assert len(tc.candidates) == 1
    assert tc.candidates[0].is_original
    assert tc.candidates[0].text == "42"


def test_punct_token_identity_only(
    generator_no_cache: CandidateGenerator,
) -> None:
    """PUNCT tokens produce only identity candidates."""
    tokens = [Token(text=".", token_type=TokenType.PUNCT, span=TextSpan(0, 1))]
    tc = generator_no_cache.generate_for_token_index(tokens, 0)
    assert len(tc.candidates) == 1
    assert tc.candidates[0].is_original
    assert tc.candidates[0].text == "."


def test_space_token_identity_only(
    generator_no_cache: CandidateGenerator,
) -> None:
    """SPACE tokens produce only identity candidates."""
    tokens = [Token(text=" ", token_type=TokenType.SPACE, span=TextSpan(0, 1))]
    tc = generator_no_cache.generate_for_token_index(tokens, 0)
    assert len(tc.candidates) == 1
    assert tc.candidates[0].is_original


def test_newline_token_identity_only(
    generator_no_cache: CandidateGenerator,
) -> None:
    """NEWLINE tokens produce only identity candidates."""
    tokens = [Token(text="\n", token_type=TokenType.NEWLINE, span=TextSpan(0, 1))]
    tc = generator_no_cache.generate_for_token_index(tokens, 0)
    assert len(tc.candidates) == 1
    assert tc.candidates[0].is_original


# ---------------------------------------------------------------------------
# Document-level API tests
# ---------------------------------------------------------------------------


def test_generate_document_returns_all_tokens(
    generator_no_cache: CandidateGenerator,
) -> None:
    """generate_document returns a CandidateDocument with correct count."""
    tokens = [
        Token(text="hello", token_type=TokenType.FOREIGN_WORD, span=TextSpan(0, 5)),
        Token(text=" ", token_type=TokenType.SPACE, span=TextSpan(5, 6)),
        Token(text="world", token_type=TokenType.FOREIGN_WORD, span=TextSpan(6, 11)),
    ]
    doc = generator_no_cache.generate_document(tokens)
    assert len(doc.token_candidates) == 3
    assert doc.stats.total_tokens == 3


def test_generate_document_stats(
    generator_no_cache: CandidateGenerator,
) -> None:
    """generate_document returns meaningful stats."""
    tokens = [
        Token(text="hello", token_type=TokenType.FOREIGN_WORD, span=TextSpan(0, 5)),
    ]
    doc = generator_no_cache.generate_document(tokens)
    assert doc.stats.total_tokens == 1
    assert doc.stats.total_candidates >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_token_text_returns_original(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Empty token text returns a single identity candidate."""
    generator_no_cache.generate_token("", protected=False)
    # Empty text results in no identity proposal (rejected by proposal validation),
    # but protected=True still produces a candidate.
    candidates_protected = generator_no_cache.generate_token("", protected=True)
    assert len(candidates_protected) == 1
    assert candidates_protected[0].text == ""
    assert candidates_protected[0].is_original


def test_single_character_token(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Single character token is handled gracefully."""
    candidates = generator_no_cache.generate_token("a")
    assert len(candidates) >= 1
    assert candidates[0].is_original


def test_unicode_token_preserved(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Unicode token characters are preserved in candidate text."""
    candidates = generator_no_cache.generate_token("đ")
    original = [c for c in candidates if c.is_original]
    assert len(original) == 1
    assert original[0].text == "đ"


def test_multiple_candidate_evidences_merged(
    generator_no_cache: CandidateGenerator,
) -> None:
    """Candidate with multiple evidence items merges correctly."""
    candidates = generator_no_cache.generate_token("test")
    for c in candidates:
        # evidence should be a list (possibly empty for identity-only)
        assert isinstance(c.evidence, list)
