"""Tests for lattice types, safety gate, and Viterbi decoder."""

from __future__ import annotations

from vn_corrector.common.lexicon import PhraseEntry, Provenance
from vn_corrector.common.scoring import Score
from vn_corrector.stage5_scorer.lattice import (
    DecodeResult,
    LatticeDecoder,
    LatticeEdge,
    compute_phrase_span_risk,
    compute_phrase_span_score,
    is_safe_phrase_restoration,
    should_accept_phrase_decode,
)


def _phrase(surface: str, no_tone: str, n: int, conf: float) -> PhraseEntry:
    return PhraseEntry(
        entry_id=f"phrase/{surface}",
        phrase=surface,
        normalized=surface,
        no_tone=no_tone,
        n=n,
        score=Score(confidence=conf, frequency=conf),
        provenance=Provenance(),
    )


class TestLatticeEdge:
    def test_lattice_edge_creation(self) -> None:
        edge = LatticeEdge(
            start=0,
            end=2,
            output_tokens=("vậy", "thì"),
            score=4.0,
            risk=0.1,
            source="phrase_span",
            raw_start=0,
            raw_end=3,
            char_start=0,
            char_end=7,
            explanation="trusted phrase",
        )
        assert edge.start == 0
        assert edge.end == 2
        assert edge.raw_start == 0
        assert edge.raw_end == 3


class TestSafetyGate:
    def test_safe_accentless_to_accented_phrase(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.98)
        assert is_safe_phrase_restoration("vay thi", phrase) is True

    def test_unsafe_already_accented_original(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.98)
        assert is_safe_phrase_restoration("vậy thì", phrase) is False

    def test_unsafe_single_token(self) -> None:
        phrase = _phrase("mà", "ma", 1, 0.99)
        assert is_safe_phrase_restoration("ma", phrase) is False

    def test_unsafe_mismatched_base(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.98)
        assert is_safe_phrase_restoration("vay khong", phrase) is False

    def test_unsafe_candidate_without_vietnamese_accents(self) -> None:
        phrase = _phrase("iphone", "iphone", 1, 0.99)
        assert is_safe_phrase_restoration("iphone", phrase) is False

    def test_unsafe_low_confidence_short_phrase(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.60)
        assert is_safe_phrase_restoration("vay thi", phrase) is False

    def test_safe_high_confidence_three_token_phrase(self) -> None:
        phrase = _phrase("làm thế nào", "lam the nao", 3, 0.95)
        assert is_safe_phrase_restoration("lam the nao", phrase) is True


class TestScoreAndRisk:
    def test_compute_score(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.98)
        score = compute_phrase_span_score(phrase)
        expected = 0.98 * (3.5 + min(2.0, 0.25 * 2))
        assert score == expected

    def test_compute_score_long_phrase(self) -> None:
        phrase = _phrase("vậy thì giờ phải làm", "vay thi gio phai lam", 5, 0.99)
        score = compute_phrase_span_score(phrase)
        expected = 0.99 * (3.5 + min(2.0, 0.25 * 5))
        assert score == expected

    def test_compute_risk_short_phrase(self) -> None:
        phrase = _phrase("vậy thì", "vay thi", 2, 0.98)
        risk = compute_phrase_span_risk(phrase, "vay thi")
        assert risk > 0.15
        assert risk <= 1.0

    def test_compute_risk_long_phrase(self) -> None:
        phrase = _phrase("làm thế nào", "lam the nao", 3, 0.98)
        risk = compute_phrase_span_risk(phrase, "lam the nao")
        assert risk <= 0.1


class TestDecodeResult:
    def test_changed_true_when_phrase_edge(self) -> None:
        result = DecodeResult(
            tokens=("vậy", "thì"),
            best_score=4.0,
            original_score=0.0,
            score_margin=4.0,
            total_risk=0.1,
            edges=(
                LatticeEdge(
                    start=0,
                    end=2,
                    output_tokens=("vậy", "thì"),
                    score=4.0,
                    risk=0.1,
                    source="phrase_span",
                ),
            ),
        )
        assert result.changed is True

    def test_changed_false_when_identity(self) -> None:
        result = DecodeResult(
            tokens=("vay", "thi"),
            best_score=0.0,
            original_score=0.0,
            score_margin=0.0,
            total_risk=0.0,
            edges=(
                LatticeEdge(
                    start=0,
                    end=1,
                    output_tokens=("vay",),
                    score=0.0,
                    risk=0.0,
                    source="identity",
                ),
                LatticeEdge(
                    start=1,
                    end=2,
                    output_tokens=("thi",),
                    score=0.0,
                    risk=0.0,
                    source="identity",
                ),
            ),
        )
        assert result.changed is False


class TestDecisionGate:
    def test_reject_unchanged(self) -> None:
        result = DecodeResult(
            tokens=("vay",),
            best_score=0.0,
            original_score=0.0,
            score_margin=0.0,
            total_risk=0.0,
            edges=(
                LatticeEdge(
                    start=0,
                    end=1,
                    output_tokens=("vay",),
                    score=0.0,
                    risk=0.0,
                    source="identity",
                ),
            ),
        )
        assert should_accept_phrase_decode(result, 2.0, 0.5) is False

    def test_accept_high_margin_low_risk(self) -> None:
        result = DecodeResult(
            tokens=("vậy", "thì"),
            best_score=4.0,
            original_score=0.0,
            score_margin=4.0,
            total_risk=0.1,
            edges=(
                LatticeEdge(
                    start=0,
                    end=2,
                    output_tokens=("vậy", "thì"),
                    score=4.0,
                    risk=0.1,
                    source="phrase_span",
                ),
            ),
        )
        assert should_accept_phrase_decode(result, 2.0, 0.5) is True

    def test_reject_low_margin(self) -> None:
        result = DecodeResult(
            tokens=("vậy", "thì"),
            best_score=1.0,
            original_score=0.0,
            score_margin=1.0,
            total_risk=0.1,
            edges=(
                LatticeEdge(
                    start=0,
                    end=2,
                    output_tokens=("vậy", "thì"),
                    score=1.0,
                    risk=0.1,
                    source="phrase_span",
                ),
            ),
        )
        assert should_accept_phrase_decode(result, 2.0, 0.5) is False

    def test_reject_high_risk(self) -> None:
        result = DecodeResult(
            tokens=("vậy", "thì"),
            best_score=4.0,
            original_score=0.0,
            score_margin=4.0,
            total_risk=0.6,
            edges=(
                LatticeEdge(
                    start=0,
                    end=2,
                    output_tokens=("vậy", "thì"),
                    score=4.0,
                    risk=0.6,
                    source="phrase_span",
                ),
            ),
        )
        assert should_accept_phrase_decode(result, 2.0, 0.5) is False


class TestLatticeDecoder:
    def test_viterbi_identity_path(self) -> None:
        edges = [
            LatticeEdge(
                start=0, end=1, output_tokens=("vay",), score=0.0, risk=0.0, source="identity"
            ),
            LatticeEdge(
                start=1, end=2, output_tokens=("thi",), score=0.0, risk=0.0, source="identity"
            ),
        ]
        result = LatticeDecoder().decode(edges, n_words=2)
        assert result.tokens == ("vay", "thi")
        assert result.changed is False

    def test_viterbi_prefers_phrase_edge(self) -> None:
        edges = [
            LatticeEdge(
                start=0, end=1, output_tokens=("vay",), score=0.0, risk=0.0, source="identity"
            ),
            LatticeEdge(
                start=1, end=2, output_tokens=("thi",), score=0.0, risk=0.0, source="identity"
            ),
            LatticeEdge(
                start=0,
                end=2,
                output_tokens=("vậy", "thì"),
                score=4.0,
                risk=0.1,
                source="phrase_span",
            ),
        ]
        result = LatticeDecoder().decode(edges, n_words=2)
        assert result.tokens == ("vậy", "thì")
        assert result.changed is True

    def test_viterbi_prefers_lower_risk_on_equal_score(self) -> None:
        edges = [
            LatticeEdge(
                start=0,
                end=2,
                output_tokens=("a", "b"),
                score=3.0,
                risk=0.5,
                source="phrase_span",
            ),
            LatticeEdge(
                start=0,
                end=2,
                output_tokens=("c", "d"),
                score=3.0,
                risk=0.1,
                source="phrase_span",
            ),
        ]
        result = LatticeDecoder().decode(edges, n_words=2)
        assert result.tokens == ("c", "d")

    def test_viterbi_combines_non_overlapping_phrase_edges(self) -> None:
        edges = [
            LatticeEdge(
                start=0,
                end=2,
                output_tokens=("vậy", "thì"),
                score=4.0,
                risk=0.1,
                source="phrase_span",
            ),
            LatticeEdge(
                start=2,
                end=4,
                output_tokens=("giờ", "phải"),
                score=3.5,
                risk=0.1,
                source="phrase_span",
            ),
        ]
        result = LatticeDecoder().decode(edges, n_words=4)
        assert result.tokens == ("vậy", "thì", "giờ", "phải")

    def test_viterbi_rejects_invalid_edge_bounds(self) -> None:
        edges = [
            LatticeEdge(
                start=0,
                end=5,
                output_tokens=("a", "b", "c"),
                score=4.0,
                risk=0.1,
                source="phrase_span",
            ),
        ]
        result = LatticeDecoder().decode(edges, n_words=3)
        # Should return empty/invalid path because edge end > n_words
        assert result.tokens == ()
        assert result.best_score == float("-inf")
