"""Tests for combination generation."""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import Candidate, TokenCandidates
from vn_corrector.stage5_scorer.combinations import generate_sequences
from vn_corrector.stage5_scorer.types import CandidateSequence, CandidateWindow


def _make_tc(text: str, candidates: list[str]) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=False,
        candidates=[
            Candidate(
                text=c,
                normalized=c,
                no_tone_key=c.lower(),
                sources=set(),
                evidence=[],
            )
            for c in candidates
        ],
    )


class TestGenerateSequences:
    def test_identity_path_preserved(self) -> None:
        tcs = [
            _make_tc("số", ["số"]),
            _make_tc("mùông", ["mùông", "muỗng"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=5000,
            max_per_token=8,
        )
        identity = tuple(tc.token_text for tc in tcs)
        assert any(s.tokens == identity for s in sequences)

    def test_simple_combinations(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=5000,
            max_per_token=8,
        )
        texts = {" ".join(s.tokens) for s in sequences}
        assert texts == {"a b", "a c"}

    def test_max_combinations_respected(self) -> None:
        tcs = [_make_tc(f"t{i}", [f"t{i}_v{j}" for j in range(10)]) for i in range(5)]
        window = CandidateWindow(start=0, end=5, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=100,
            max_per_token=3,
        )
        assert len(sequences) <= 100

    def test_empty_window(self) -> None:
        window = CandidateWindow(start=0, end=0, token_candidates=[])
        sequences = generate_sequences(
            window,
            max_combinations=5000,
            max_per_token=8,
        )
        assert len(sequences) == 0

    def test_returns_candidate_sequences(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=5000,
            max_per_token=8,
        )
        assert all(isinstance(s, CandidateSequence) for s in sequences)

    def test_single_token_no_alternatives(self) -> None:
        tcs = [_make_tc("a", ["a"])]
        window = CandidateWindow(start=0, end=1, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=5000,
            max_per_token=8,
        )
        assert len(sequences) == 1
        assert sequences[0].tokens == ("a",)
