"""Tests for combination generation."""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import Candidate, TokenCandidates
from vn_corrector.stage5_scorer.combinations import beam_search_sequences, generate_sequences
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

    def test_max_combinations_respected_with_many_positions(self) -> None:
        """Regression: with 30+ positions each having 2 candidates,
        the total product (2^30 = 1B+) must be capped by max_combinations.
        """
        tcs = [_make_tc(f"t{i}", [f"t{i}_a", f"t{i}_b"]) for i in range(30)]
        window = CandidateWindow(start=0, end=30, token_candidates=tcs)
        sequences = generate_sequences(
            window,
            max_combinations=250,
            max_per_token=2,
        )
        assert len(sequences) <= 250
        # Also verify it completes quickly — no combinatorial explosion
        assert len(sequences) > 0
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

    def test_truncation_keeps_highest_prior_alternatives(self) -> None:
        """When max_combinations forces pruning, keep best by prior_score.

        Regression for accentless_004: "do" has độ(0.360) as the best candidate
        but it is 4th in storage order; đợ(0.270) is 1st. Without sorting by
        prior_score, độ would be dropped when pruning.
        """
        tc_neu = _make_tc("neu", ["neu", "nều", "nếu", "nêu"])
        tc_do = _make_tc("do", ["do", "đợ", "đỡ", "đờ", "độ", "đỗ", "đổ", "đồ"])
        tc_am = _make_tc("am", ["am", "ậm", "ẫm", "ẩm", "ầm", "ấm", "ảm", "ạm"])
        tc_vua = _make_tc("vua", ["vua", "vừa"])
        tc_du = _make_tc("du", ["du", "đủ"])

        _set_prior(tc_neu, {"nếu": 0.35, "nều": 0.26, "nêu": 0.28})
        _set_prior(
            tc_do,
            {"độ": 0.36, "đồ": 0.32, "đổ": 0.30, "đỡ": 0.29, "đỗ": 0.29, "đờ": 0.28, "đợ": 0.27},
        )
        _set_prior(tc_am, {"ấm": 0.32, "ẩm": 0.29, "ầm": 0.28, "ậm": 0.26})
        _set_prior(tc_vua, {"vừa": 0.34})
        _set_prior(tc_du, {"đủ": 0.35})

        tcs = [tc_neu, tc_do, tc_am, tc_vua, tc_du]
        window = CandidateWindow(start=0, end=5, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=100)

        do_position = {seq.tokens[1] for seq in sequences}

        assert "độ" in do_position, (
            f"Best alternative 'độ'(prior=0.36) was pruned; only got {do_position}"
        )
        assert "đợ" not in do_position, (
            f"Worst alternative 'đợ'(prior=0.27) survived pruning; got {do_position}"
        )


def _set_prior(tc: TokenCandidates, priors: dict[str, float]) -> None:
    """Set prior_score on candidates matching *priors* keys."""
    for cand in tc.candidates:
        if cand.text in priors:
            cand.prior_score = priors[cand.text]


class TestBeamSearch:
    """Tests for beam_search_sequences."""

    def test_identity_path_preserved(self) -> None:
        tcs = [
            _make_tc("số", ["số"]),
            _make_tc("mùông", ["mùông", "muỗng"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = beam_search_sequences(window, beam_size=32, max_candidates_per_token=8)
        identity = tuple(tc.token_text for tc in tcs)
        assert any(s.tokens == identity for s in sequences)

    def test_simple_combinations(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = beam_search_sequences(window, beam_size=32, max_candidates_per_token=8)
        texts = {" ".join(s.tokens) for s in sequences}
        assert texts == {"a b", "a c"}

    def test_beam_size_respected(self) -> None:
        """With many candidates, beam at least produces beam_size sequences."""
        tcs = [_make_tc(f"t{i}", [f"t{i}_v{j}" for j in range(10)]) for i in range(5)]
        window = CandidateWindow(start=0, end=5, token_candidates=tcs)
        sequences = beam_search_sequences(window, beam_size=16, max_candidates_per_token=8)
        assert len(sequences) > 0

    def test_ngram_bonus_alters_ranking(self) -> None:
        """ngram_score_fn rewards contextually correct partial sequences."""
        neu_cands = [
            Candidate(
                text="neu",
                normalized="neu",
                no_tone_key="neu",
                sources=set(),
                evidence=[],
                prior_score=0.1,
                is_original=True,
            ),
            Candidate(
                text="nếu",
                normalized="nếu",
                no_tone_key="neu",
                sources=set(),
                evidence=[],
                prior_score=0.3,
            ),
            Candidate(
                text="nều",
                normalized="nều",
                no_tone_key="neu",
                sources=set(),
                evidence=[],
                prior_score=0.2,
            ),
        ]
        do_cands = [
            Candidate(
                text="do",
                normalized="do",
                no_tone_key="do",
                sources=set(),
                evidence=[],
                prior_score=0.1,
                is_original=True,
            ),
            Candidate(
                text="độ",
                normalized="độ",
                no_tone_key="do",
                sources=set(),
                evidence=[],
                prior_score=0.35,
            ),
            Candidate(
                text="đồ",
                normalized="đồ",
                no_tone_key="do",
                sources=set(),
                evidence=[],
                prior_score=0.3,
            ),
            Candidate(
                text="đợ",
                normalized="đợ",
                no_tone_key="do",
                sources=set(),
                evidence=[],
                prior_score=0.25,
            ),
        ]
        tcs = [
            TokenCandidates(token_text="neu", token_index=0, protected=False, candidates=neu_cands),
            TokenCandidates(token_text="do", token_index=1, protected=False, candidates=do_cands),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)

        sequences_no_ngram = beam_search_sequences(window, beam_size=32, max_candidates_per_token=4)

        sequences_ngram = beam_search_sequences(
            window,
            beam_size=32,
            max_candidates_per_token=4,
            ngram_score_fn=lambda _l, _r: 0.0,
        )

        assert len(sequences_no_ngram) > 0
        assert len(sequences_ngram) > 0

    def test_empty_window(self) -> None:
        window = CandidateWindow(start=0, end=0, token_candidates=[])
        sequences = beam_search_sequences(window, beam_size=32, max_candidates_per_token=8)
        assert len(sequences) == 0

    def test_single_token_no_alternatives(self) -> None:
        tcs = [_make_tc("a", ["a"])]
        window = CandidateWindow(start=0, end=1, token_candidates=tcs)
        sequences = beam_search_sequences(window, beam_size=32, max_candidates_per_token=8)
        assert len(sequences) == 1
        assert sequences[0].tokens == ("a",)

    def test_returns_candidate_sequences(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = beam_search_sequences(window, beam_size=32, max_candidates_per_token=8)
        assert all(isinstance(s, CandidateSequence) for s in sequences)
