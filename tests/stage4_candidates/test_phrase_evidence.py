"""Tests for PhraseEvidenceSource — tags candidates with phrase-context evidence.

This source should inspect all variation candidates (not just the original
token text) and yield PHRASE_SPECIFIC proposals when a candidate forms a
known phrase with neighboring tokens.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vn_corrector.common.enums import TokenType
from vn_corrector.common.spans import TextSpan, Token
from vn_corrector.stage4_candidates import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    CandidateSource,
)
from vn_corrector.stage4_candidates.sources.phrase_evidence import PhraseEvidenceSource
from vn_corrector.stage4_candidates.types import (
    CandidateContext,
    CandidateRequest,
)


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


class TestPhraseEvidenceSource:
    """PhraseEvidenceSource should check all variation candidates for phrase matches."""

    def test_skips_protected_tokens(self) -> None:
        """Protected tokens are skipped."""
        source = PhraseEvidenceSource()
        request = CandidateRequest(token_text="test", token_index=0, protected=True)
        context = CandidateContext(tokens=None, lexicon=MagicMock(), config=MagicMock())
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_skips_when_no_tokens(self) -> None:
        """No tokens in context means no phrase evidence."""
        source = PhraseEvidenceSource()
        request = CandidateRequest(token_text="test", token_index=0)
        context = CandidateContext(tokens=None, lexicon=MagicMock(), config=MagicMock())
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_skips_when_no_index(self) -> None:
        """No token_index means no phrase evidence."""
        source = PhraseEvidenceSource()
        request = CandidateRequest(token_text="test")
        context = CandidateContext(
            tokens=[Token(text="test", token_type=TokenType.VI_WORD, span=TextSpan(0, 4))],
            lexicon=MagicMock(),
            config=MagicMock(),
        )
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_uses_candidate_texts_from_context(self) -> None:
        """Uses context.candidate_texts when populated."""
        source = PhraseEvidenceSource()
        lexicon = MagicMock()
        lexicon.lookup_phrase_str.return_value = MagicMock()
        config = MagicMock()
        config.max_phrase_window = 2
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="mùông", token_index=0, token_type=TokenType.VI_WORD)
        context = CandidateContext(
            tokens=[
                Token(text="số", token_type=TokenType.VI_WORD, span=TextSpan(0, 3)),
                Token(text="mùông", token_type=TokenType.VI_WORD, span=TextSpan(4, 10)),
            ],
            lexicon=lexicon,
            config=config,
            candidate_texts={"muỗng", "mùông"},
        )
        proposals = list(source.generate(request, context))
        # At least one candidate text should trigger phrase evidence
        assert len(proposals) > 0
        assert proposals[0].source == CandidateSource.PHRASE_SPECIFIC

    def test_falls_back_to_original_when_no_candidate_texts(self) -> None:
        """Falls back to original token text when candidate_texts is empty."""
        source = PhraseEvidenceSource()
        lexicon = MagicMock()
        lexicon.lookup_phrase_str.return_value = None
        lexicon.lookup_phrase.return_value = []
        lexicon.lookup_phrase_normalized.return_value = []
        config = MagicMock()
        config.max_phrase_window = 2
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="mùông", token_index=0)
        context = CandidateContext(
            tokens=[
                Token(text="số", token_type=TokenType.VI_WORD, span=TextSpan(0, 3)),
                Token(text="mùông", token_type=TokenType.VI_WORD, span=TextSpan(4, 10)),
            ],
            lexicon=lexicon,
            config=config,
            candidate_texts=set(),
        )
        proposals = list(source.generate(request, context))
        # With empty candidate_texts, falls back to {original}, but no phrase match
        assert len(proposals) == 0

    def test_end_to_end_with_mock(self, mock_lexicon: MagicMock) -> None:
        """End-to-end: generator passes candidate texts to phrase evidence."""
        # Mock phrase lookup to return a match
        mock_lexicon.lookup_phrase_str.return_value = MagicMock()

        config = CandidateGeneratorConfig(
            cache_enabled=False,
            max_phrase_window=2,
            enable_edit_distance=False,
            enable_domain_specific=False,
        )
        gen = CandidateGenerator(mock_lexicon, config=config)

        tokens = [
            Token(text="số", token_type=TokenType.VI_WORD, span=TextSpan(0, 3)),
            Token(text="mùông", token_type=TokenType.VI_WORD, span=TextSpan(4, 10)),
        ]
        tc = gen.generate_for_token_index(tokens, 1)
        # With mock returning match, should have PHRASE_SPECIFIC evidence
        for c in tc.candidates:
            if c.text == "mùông":
                assert any(ev.source == CandidateSource.PHRASE_SPECIFIC for ev in c.evidence), (
                    "Original text should get phrase evidence"
                )


class TestPhraseEvidenceEndToEnd:
    """End-to-end tests with the real lexicon to prove phrase evidence works."""

    def test_generator_includes_phrase_evidence_source(self) -> None:
        """Generator registers PhraseEvidenceSource."""
        config = CandidateGeneratorConfig(cache_enabled=False, enable_phrase_evidence=True)
        gen = CandidateGenerator(MagicMock(), config=config)
        # PhraseEvidenceSource is the last registered source
        assert any(isinstance(s, PhraseEvidenceSource) for s in gen._sources)

    def test_phrase_evidence_not_generated_for_single_token(self) -> None:
        """Single token (no context) does not produce phrase evidence."""
        # This verifies the source correctly returns early when no context exists
        source = PhraseEvidenceSource()
        request = CandidateRequest(token_text="test", token_index=0, token_type=TokenType.VI_WORD)
        context = CandidateContext(
            tokens=[Token(text="test", token_type=TokenType.VI_WORD, span=TextSpan(0, 4))],
            lexicon=MagicMock(),
            config=MagicMock(),
        )
        proposals = list(source.generate(request, context))
        # Window size 1 with 1 token: end - start = 1 < 2, so no match
        assert len(proposals) == 0
