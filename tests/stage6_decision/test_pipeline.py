"""Integration tests for M6 pipeline — decide_scored_window."""

from dataclasses import dataclass, field
from typing import cast

from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
)
from vn_corrector.stage6_decision.pipeline import decide_scored_window
from vn_corrector.stage6_decision.types import (
    DecisionReason,
    DecisionType,
)


class TestPipeline:
    def test_happy_path_accepts_best(self):
        """Accept high-confidence correction with good margin."""
        window = _make_window_3tok()
        seq1 = _make_seq(("số", "muỗng", "gạt"), ("số", "mùông", "gạt"), 0.92)
        seq2 = _make_seq(("số", "mường", "gạt"), ("số", "mùông", "gạt"), 0.50)
        scored = ScoredWindow(window=window, ranked_sequences=[seq1, seq2])

        decisions, changes, flags = decide_scored_window(scored)

        assert len(decisions) == 3
        assert len(changes) == 1  # only "muỗng" changed
        assert len(flags) == 0

        d = decisions[1]  # position 1 = "mùông" → "muỗng"
        assert d.decision == DecisionType.ACCEPT
        assert d.reason == DecisionReason.ACCEPTED
        assert d.original == "mùông"
        assert d.best == "muỗng"

        change = changes[0]
        assert change.original == "mùông"
        assert change.replacement == "muỗng"

    def test_protected_token_not_changed(self):
        """Protected tokens produce REJECT and no changes."""
        window = _make_window_3tok(protected_positions={1})
        seq1 = _make_seq(("số", "0987654321", "gạt"), ("số", "0987654321", "gạt"), 0.95)
        scored = ScoredWindow(window=window, ranked_sequences=[seq1])

        decisions, changes, _flags = decide_scored_window(scored)

        d = decisions[1]
        assert d.decision == DecisionType.REJECT
        assert d.reason == DecisionReason.PROTECTED
        assert not changes  # no changes for protected

    def test_no_ranked_sequences(self):
        """Empty ranked sequences produce REJECT with appropriate reason."""
        window = _make_window_3tok()
        scored = ScoredWindow(window=window, ranked_sequences=[])

        decisions, changes, flags = decide_scored_window(scored)

        assert len(decisions) == 3
        assert all(d.decision == DecisionType.REJECT for d in decisions)
        assert all(d.reason == DecisionReason.NO_RANKED_SEQUENCE for d in decisions)
        assert not changes
        assert not flags

    def test_identity_tokens(self):
        """All-identity tokens produce no changes."""
        window = _make_window_3tok()
        seq1 = _make_seq(("số", "muỗng", "gạt"), ("số", "muỗng", "gạt"), 0.95)
        scored = ScoredWindow(window=window, ranked_sequences=[seq1])

        decisions, changes, flags = decide_scored_window(scored)

        assert all(d.decision == DecisionType.REJECT for d in decisions)
        assert all(d.reason == DecisionReason.IDENTITY for d in decisions)
        assert not changes
        assert not flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeTokenCandidates:
    """Minimal token candidates stub for pipeline tests."""

    token_text: str
    token_index: int
    protected: bool
    candidates: list[object] = field(default_factory=list)


def _make_window_3tok(
    protected_positions: set[int] | None = None,
) -> CandidateWindow:
    protected_positions = protected_positions or set()
    return CandidateWindow(
        start=0,
        end=15,
        token_candidates=cast(
            "list[TokenCandidates]",
            [
                FakeTokenCandidates("số", 0, False),
                FakeTokenCandidates("mùông", 1, 1 in protected_positions),
                FakeTokenCandidates("gạt", 2, False),
            ],
        ),
    )


def _make_seq(
    tokens: tuple[str, ...],
    originals: tuple[str, ...],
    confidence: float,
) -> ScoredSequence:
    changed = tuple(i for i, (t, o) in enumerate(zip(tokens, originals, strict=False)) if t != o)
    return ScoredSequence(
        sequence=CandidateSequence(
            tokens=tokens,
            original_tokens=originals,
            changed_positions=changed,
        ),
        breakdown=ScoreBreakdown(),
        confidence=confidence,
        explanations=[],
    )
