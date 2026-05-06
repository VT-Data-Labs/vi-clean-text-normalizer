"""Tests for limit enforcement in Stage 4 candidate generation.

Tests the trimming helper and combination-count estimation.
"""

from __future__ import annotations

from vn_corrector.stage4_candidates import (
    Candidate,
    CandidateGeneratorConfig,
    CandidateSource,
)
from vn_corrector.stage4_candidates.limits import (
    estimate_combination_count,
    trim_candidate_list,
    trim_window_token_candidates,
)
from vn_corrector.stage4_candidates.types import (
    CandidateEvidence,
    TokenCandidates,
)


def _make_candidate(text: str, is_original: bool = False) -> Candidate:
    return Candidate(
        text=text,
        normalized=text.lower(),
        no_tone_key=text.lower(),
        sources={CandidateSource.ORIGINAL if is_original else CandidateSource.SYLLABLE_MAP},
        evidence=[
            CandidateEvidence(
                source=CandidateSource.ORIGINAL if is_original else CandidateSource.SYLLABLE_MAP,
                detail="test",
            )
        ],
        is_original=is_original,
    )


class TestEstimateCombinationCount:
    def test_empty_list(self) -> None:
        assert estimate_combination_count([]) == 0

    def test_single_token(self) -> None:
        tc = TokenCandidates("hello", 0, False, [_make_candidate("hello", True)])
        assert estimate_combination_count([tc]) == 1

    def test_multiple_tokens(self) -> None:
        tcs = [
            TokenCandidates("a", 0, False, [_make_candidate("a", True), _make_candidate("b")]),
            TokenCandidates(
                "c",
                1,
                False,
                [_make_candidate("c", True), _make_candidate("d"), _make_candidate("e")],
            ),
        ]
        assert estimate_combination_count(tcs) == 6  # 2 * 3

    def test_zero_candidates(self) -> None:
        tc = TokenCandidates("a", 0, False, [])
        assert estimate_combination_count([tc]) == 0


class TestTrimCandidateList:
    def test_under_limit(self) -> None:
        weights = {"original": 0.1, "syllable_map": 0.2}
        candidates = [
            _make_candidate("a", True),
            _make_candidate("b"),
        ]
        result = trim_candidate_list(candidates, 5, weights)
        assert len(result) == 2

    def test_at_limit(self) -> None:
        weights = {"original": 0.1, "syllable_map": 0.2}
        candidates = [
            _make_candidate("a", True),
            _make_candidate("b"),
            _make_candidate("c"),
        ]
        result = trim_candidate_list(candidates, 3, weights)
        assert len(result) == 3

    def test_over_limit(self) -> None:
        weights = {"original": 0.1, "syllable_map": 0.2}
        candidates = [
            _make_candidate("a", True),
            _make_candidate("b"),
            _make_candidate("c"),
            _make_candidate("d"),
        ]
        result = trim_candidate_list(candidates, 2, weights)
        assert len(result) == 2

    def test_original_preserved_when_over_limit(self) -> None:
        weights = {"original": 0.1, "syllable_map": 0.2}
        candidates = [
            _make_candidate("a", True),
            _make_candidate("b"),
            _make_candidate("c"),
            _make_candidate("d"),
        ]
        result = trim_candidate_list(candidates, 2, weights, keep_original=True)
        assert len(result) == 2
        assert result[0].is_original

    def test_no_original_preserved_if_none(self) -> None:
        weights = {"original": 0.1, "syllable_map": 0.2}
        candidates = [_make_candidate("b"), _make_candidate("c")]
        result = trim_candidate_list(candidates, 1, weights, keep_original=True)
        assert len(result) == 1


class TestTrimWindowTokenCandidates:
    def test_under_combination_limit(self) -> None:
        config = CandidateGeneratorConfig(
            max_candidates_per_token=8,
            max_candidate_combinations_per_window=100,
            keep_original_first=True,
        )
        tcs = [
            TokenCandidates("a", 0, False, [_make_candidate("a", True), _make_candidate("b")]),
            TokenCandidates("c", 1, False, [_make_candidate("c", True), _make_candidate("d")]),
        ]
        result = trim_window_token_candidates(tcs, 100, config)
        assert len(result[0].candidates) == 2
        assert len(result[1].candidates) == 2

    def test_over_combination_limit_trims(self) -> None:
        config = CandidateGeneratorConfig(
            max_candidates_per_token=8,
            max_candidate_combinations_per_window=10,
            source_prior_weights={"original": 0.1, "syllable_map": 0.2},
            keep_original_first=True,
        )
        tcs = [
            TokenCandidates(
                "a",
                0,
                False,
                [
                    _make_candidate("a", True),
                    _make_candidate("b"),
                    _make_candidate("c"),
                    _make_candidate("d"),
                ],
            ),
            TokenCandidates(
                "e",
                1,
                False,
                [
                    _make_candidate("e", True),
                    _make_candidate("f"),
                    _make_candidate("g"),
                ],
            ),
        ]
        # 4 * 3 = 12 > 10, should trim
        result = trim_window_token_candidates(list(tcs), 10, config)
        combos = estimate_combination_count(result)
        assert combos <= 10, f"Combinations {combos} > 10"

    def test_original_preserved_during_trim(self) -> None:
        config = CandidateGeneratorConfig(
            max_candidates_per_token=8,
            max_candidate_combinations_per_window=1,
            source_prior_weights={"original": 0.1, "syllable_map": 0.2},
            keep_original_first=True,
        )
        tcs = [
            TokenCandidates(
                "a",
                0,
                False,
                [
                    _make_candidate("a", True),
                    _make_candidate("b"),
                ],
            ),
            TokenCandidates(
                "c",
                1,
                False,
                [
                    _make_candidate("c", True),
                    _make_candidate("d"),
                ],
            ),
        ]
        result = trim_window_token_candidates(list(tcs), 1, config)
        # After trimming to 1 combination, each should have 1 candidate (original)
        for tc in result:
            assert len(tc.candidates) >= 1
            assert tc.candidates[0].is_original
