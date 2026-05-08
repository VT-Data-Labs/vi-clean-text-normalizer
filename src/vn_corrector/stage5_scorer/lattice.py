"""Lattice types, safety gate, and Viterbi decoder for phrase-span restoration.

Provides:

* :class:`LatticeEdge` — a weighted edge in the phrase restoration lattice.
* :class:`DecodeResult` — the output of a Viterbi decode.
* :class:`LatticeDecoder` — Viterbi-style DP over word-position lattice edges.
* :func:`is_safe_phrase_restoration` — safety gate for phrase-span corrections.
* :func:`get_phrase_surface` — helper to extract surface text from a phrase entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vn_corrector.common.lexicon import PhraseEntry
from vn_corrector.stage1_normalize import strip_accents
from vn_corrector.utils.unicode import contains_vietnamese


def get_phrase_surface(phrase: PhraseEntry) -> str:
    """Return the canonical surface text of a phrase entry."""
    return phrase.phrase


@dataclass(frozen=True)
class LatticeEdge:
    """A weighted edge in the phrase restoration lattice.

    ``start`` / ``end`` are word-island positions.
    ``raw_start`` / ``raw_end`` are raw token positions for reconstruction.
    ``char_start`` / ``char_end`` are source character offsets.
    """

    start: int
    end: int
    output_tokens: tuple[str, ...]
    score: float
    risk: float
    source: Literal["identity", "single_candidate", "phrase_span"]
    raw_start: int | None = None
    raw_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    phrase: PhraseEntry | None = None
    explanation: str = ""


@dataclass(frozen=True)
class DecodeResult:
    """Output of a :class:`LatticeDecoder` decode run."""

    tokens: tuple[str, ...]
    best_score: float
    original_score: float
    score_margin: float
    total_risk: float
    edges: tuple[LatticeEdge, ...]

    @property
    def changed(self) -> bool:
        return any(edge.source != "identity" for edge in self.edges)


def is_safe_phrase_restoration(original_span: str, phrase: PhraseEntry) -> bool:
    """Return ``True`` if *phrase* can safely restore an accentless *original_span*.

    Rules
    -----
    1. ``strip_accents(phrase_surface).lower() == strip_accents(original_span).lower()``
    2. Phrase surface contains Vietnamese accented characters.
    3. Original span contains **no** Vietnamese accented characters.
    4. Phrase has at least 2 tokens.
    5. Phrase confidence/frequency passes threshold.
    """
    surface = get_phrase_surface(phrase)
    original_key = strip_accents(original_span).lower().strip()
    phrase_key = strip_accents(surface).lower().strip()

    if phrase_key != original_key:
        return False
    if not contains_vietnamese(surface):
        return False
    if contains_vietnamese(original_span):
        return False

    n = phrase.n
    if n < 2:
        return False

    confidence = phrase.score.confidence

    if confidence >= 0.95 and n >= 3:
        return True
    return bool(confidence >= 0.85 and n >= 2)


def compute_phrase_span_score(phrase: PhraseEntry) -> float:
    """Compute a lattice-edge score for a phrase-span edge.

    Formula: ``confidence * (3.5 + min(2.0, 0.25 * n))``
    """
    n = phrase.n or len(get_phrase_surface(phrase).split())
    base = 3.5
    length_bonus = min(2.0, 0.25 * n)
    return phrase.score.confidence * (base + length_bonus)


def compute_phrase_span_risk(phrase: PhraseEntry, _original_span: str) -> float:
    """Compute a risk score (0-1) for a phrase-span correction.

    Short phrases (n=2) get an ambiguity risk bump.
    """
    n = phrase.n or len(get_phrase_surface(phrase).split())
    confidence = phrase.score.confidence
    risk = max(0.0, 1.0 - confidence)
    if n == 2:
        risk += 0.15
    return min(1.0, risk)


def should_accept_phrase_decode(
    result: DecodeResult,
    accept_margin: float,
    risk_threshold: float,
) -> bool:
    """Decision gate: accept a phrase decode result only if margin and risk pass."""
    if not result.changed:
        return False
    if result.score_margin < accept_margin:
        return False
    return not result.total_risk > risk_threshold


class LatticeDecoder:
    """Viterbi-style decoder over word-position lattice edges.

    ``n_words`` is the number of word tokens in the island.
    Edges must use word-island positions (``start`` / ``end``).
    """

    def decode(self, edges: list[LatticeEdge], n_words: int) -> DecodeResult:
        edges_by_start: dict[int, list[LatticeEdge]] = {}
        for edge in edges:
            edges_by_start.setdefault(edge.start, []).append(edge)

        best_score = [float("-inf")] * (n_words + 1)
        best_risk = [float("inf")] * (n_words + 1)
        best_edge: list[LatticeEdge | None] = [None] * (n_words + 1)

        best_score[0] = 0.0
        best_risk[0] = 0.0

        for i in range(n_words):
            if best_score[i] == float("-inf"):
                continue
            for edge in edges_by_start.get(i, []):
                j = edge.end
                if j <= i or j > n_words:
                    continue
                new_score = best_score[i] + edge.score
                new_risk = best_risk[i] + edge.risk
                if new_score > best_score[j] or (
                    new_score == best_score[j] and new_risk < best_risk[j]
                ):
                    best_score[j] = new_score
                    best_risk[j] = new_risk
                    best_edge[j] = edge

        result_edges: list[LatticeEdge] = []
        pos = n_words
        while pos > 0:
            best = best_edge[pos]
            if best is None:
                return DecodeResult(
                    tokens=(),
                    best_score=float("-inf"),
                    original_score=0.0,
                    score_margin=float("-inf"),
                    total_risk=float("inf"),
                    edges=(),
                )
            result_edges.append(best)
            pos = best.start

        result_edges.reverse()

        tokens: list[str] = []
        for edge in result_edges:
            tokens.extend(edge.output_tokens)

        original_score = 0.0
        score_margin = best_score[n_words] - original_score

        return DecodeResult(
            tokens=tuple(tokens),
            best_score=best_score[n_words],
            original_score=original_score,
            score_margin=score_margin,
            total_risk=best_risk[n_words],
            edges=tuple(result_edges),
        )
