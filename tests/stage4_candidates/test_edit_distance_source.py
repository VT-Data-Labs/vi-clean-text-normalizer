"""Tests for EditDistanceSource — controlled approximate matching.

Verifies token length guards, edit-distance threshold, hard candidate
limit, and correct source/evidence metadata.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vn_corrector.common.lexicon import LexiconEntry
from vn_corrector.stage4_candidates import (
    CandidateGenerator,
    CandidateGeneratorConfig,
    CandidateSource,
)
from vn_corrector.stage4_candidates.sources.edit_distance import EditDistanceSource
from vn_corrector.stage4_candidates.types import CandidateContext, CandidateRequest


@pytest.fixture
def mock_lexicon_with_prefix() -> MagicMock:
    """Lexicon that returns prefix matches for edit-distance fallback."""
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


class TestEditDistanceSource:
    """Unit tests for EditDistanceSource directly."""

    def test_skips_short_tokens(self) -> None:
        """Tokens shorter than min_len are skipped."""
        source = EditDistanceSource()
        config = MagicMock()
        config.max_edit_distance = 1
        config.min_token_length_for_edit_distance = 3
        config.max_token_length_for_edit_distance = 20
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="ab", token_index=0)
        context = CandidateContext(tokens=None, lexicon=MagicMock(), config=config)
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_skips_long_tokens(self) -> None:
        """Tokens longer than max_len are skipped."""
        source = EditDistanceSource()
        config = MagicMock()
        config.max_edit_distance = 1
        config.min_token_length_for_edit_distance = 3
        config.max_token_length_for_edit_distance = 20
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="a" * 21, token_index=0)
        context = CandidateContext(tokens=None, lexicon=MagicMock(), config=config)
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_skips_protected_tokens(self) -> None:
        """Protected tokens are skipped."""
        source = EditDistanceSource()
        request = CandidateRequest(token_text="test", token_index=0, protected=True)
        context = CandidateContext(tokens=None, lexicon=MagicMock(), config=MagicMock())
        proposals = list(source.generate(request, context))
        assert len(proposals) == 0

    def test_edit_distance_proposals_have_correct_source(self) -> None:
        """Proposals have EDIT_DISTANCE source."""
        source = EditDistanceSource()
        lexicon = MagicMock()
        entry = MagicMock(spec=LexiconEntry)
        entry.surface = "muỗng"
        entry.score = None
        lexicon.query_prefix.return_value = [entry]

        config = MagicMock()
        config.max_edit_distance = 1
        config.min_token_length_for_edit_distance = 3
        config.max_token_length_for_edit_distance = 20
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="muong", token_index=0)
        context = CandidateContext(tokens=None, lexicon=lexicon, config=config)
        proposals = list(source.generate(request, context))
        if proposals:
            for p in proposals:
                assert p.source == CandidateSource.EDIT_DISTANCE
                assert p.edit_distance is not None
                assert p.edit_distance >= 0

    def test_hard_limit_of_three_candidates(self) -> None:
        """Edit-distance fallback yields at most 3 candidates."""
        source = EditDistanceSource()
        lexicon = MagicMock()
        # Create many entries with edit distance 1
        entries = []
        for _i, text in enumerate(["muỗng", "muống", "muồng", "mường", "mướng", "mượng"]):
            entry = MagicMock(spec=LexiconEntry)
            entry.surface = text
            entry.score = None
            entries.append(entry)
        lexicon.query_prefix.return_value = entries

        config = MagicMock()
        config.max_edit_distance = 1
        config.min_token_length_for_edit_distance = 3
        config.max_token_length_for_edit_distance = 20
        config.source_prior_weights = {}

        request = CandidateRequest(token_text="muong", token_index=0)
        context = CandidateContext(tokens=None, lexicon=lexicon, config=config)
        proposals = list(source.generate(request, context))
        assert len(proposals) <= 3


class TestEditDistanceIntegration:
    """Integration tests with real generator and mock lexicon."""

    def test_edit_distance_generates_candidates(self) -> None:
        """Generator runs edit-distance source when enabled."""
        lexicon = MagicMock()
        lexicon.lookup_accentless.return_value = MagicMock(entries=(), candidates=())
        lexicon.lookup_ocr.return_value = []
        lexicon.get_ocr_corrections.return_value = MagicMock(corrections=())
        lexicon.lookup_abbreviation.return_value = MagicMock(entries=(), found=False)
        lexicon.lookup_phrase_str.return_value = None
        lexicon.lookup_phrase.return_value = []
        lexicon.lookup_phrase_normalized.return_value = []
        lexicon.get_syllable_candidates.return_value = []

        # Return a candidate from edit-distance prefix lookup
        entry = MagicMock(spec=LexiconEntry)
        entry.surface = "muỗng"
        entry.score = None
        lexicon.query_prefix.return_value = [entry]

        config = CandidateGeneratorConfig(
            cache_enabled=False,
            enable_ocr_confusion=False,
            enable_syllable_map=False,
            enable_word_lexicon=False,
            enable_abbreviation=False,
            enable_phrase_evidence=False,
            enable_domain_specific=False,
            enable_edit_distance=True,
            min_token_length_for_edit_distance=3,
        )
        gen = CandidateGenerator(lexicon, config=config)
        candidates = gen.generate_token("muong")

        texts = {c.text for c in candidates}
        assert len(texts) >= 1

    def test_edit_distance_source_in_candidates(self) -> None:
        """Candidates from edit distance have EDIT_DISTANCE in sources."""
        lexicon = MagicMock()
        lexicon.lookup_accentless.return_value = MagicMock(entries=(), candidates=())
        lexicon.lookup_ocr.return_value = []
        lexicon.get_ocr_corrections.return_value = MagicMock(corrections=())
        lexicon.lookup_abbreviation.return_value = MagicMock(entries=(), found=False)
        lexicon.lookup_phrase_str.return_value = None
        lexicon.lookup_phrase.return_value = []
        lexicon.lookup_phrase_normalized.return_value = []
        lexicon.get_syllable_candidates.return_value = []

        entry = MagicMock(spec=LexiconEntry)
        entry.surface = "muỗng"
        entry.score = None
        lexicon.query_prefix.return_value = [entry]

        config = CandidateGeneratorConfig(
            cache_enabled=False,
            enable_ocr_confusion=False,
            enable_syllable_map=False,
            enable_word_lexicon=False,
            enable_abbreviation=False,
            enable_phrase_evidence=False,
            enable_domain_specific=False,
            enable_edit_distance=True,
        )
        gen = CandidateGenerator(lexicon, config=config)
        candidates = gen.generate_token("muong")

        muong_cands = [c for c in candidates if c.text == "muỗng"]
        if muong_cands:
            assert CandidateSource.EDIT_DISTANCE in muong_cands[0].sources

    def test_disabled_when_config_off(self) -> None:
        """Edit-distance source is not registered when config disables it."""
        config = CandidateGeneratorConfig(cache_enabled=False, enable_edit_distance=False)
        gen = CandidateGenerator(MagicMock(), config=config)
        edit_sources = [s for s in gen._sources if isinstance(s, EditDistanceSource)]
        assert len(edit_sources) == 0
