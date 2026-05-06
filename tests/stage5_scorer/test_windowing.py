"""Tests for windowing logic."""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import Candidate, TokenCandidates
from vn_corrector.stage5_scorer.windowing import build_windows


def _make_tc(
    text: str,
    candidates: list[str],
    protected: bool = False,
) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=protected,
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


class TestBuildWindows:
    def test_single_ambiguous_token(self) -> None:
        tcs = [
            _make_tc("số", ["số"]),
            _make_tc("mùông", ["mùông", "muỗng", "muông"]),
            _make_tc("gạt", ["gạt"]),
            _make_tc("ngang", ["ngang"]),
        ]
        windows = build_windows(tcs, max_tokens_per_window=7)
        assert len(windows) >= 1
        w = windows[0]
        assert w.start == 0
        assert w.end >= 3

    def test_no_ambiguous_token(self) -> None:
        tcs = [_make_tc("số", ["số"]), _make_tc("gạt", ["gạt"])]
        windows = build_windows(tcs, max_tokens_per_window=7)
        assert len(windows) == 0

    def test_window_clamped_to_max(self) -> None:
        tokens = [_make_tc(f"t{i}", [f"t{i}"]) for i in range(20)]
        tokens[10] = _make_tc("x", ["x", "y"])
        windows = build_windows(tokens, max_tokens_per_window=7)
        for w in windows:
            assert w.end - w.start <= 7

    def test_protected_token_ignored(self) -> None:
        tcs = [
            _make_tc("số", ["số"]),
            _make_tc("abc", ["abc"], protected=True),
            _make_tc("mùông", ["mùông", "muỗng"]),
        ]
        windows = build_windows(tcs, max_tokens_per_window=7)
        assert len(windows) >= 1

    def test_overlapping_windows_merged(self) -> None:
        tcs = [_make_tc("a", ["a"]) for _ in range(10)]
        tcs[3] = _make_tc("x", ["x", "y"])
        tcs[5] = _make_tc("z", ["z", "w"])
        windows = build_windows(tcs, max_tokens_per_window=7)
        merged_starts = [w.start for w in windows]
        assert len(merged_starts) <= 2
