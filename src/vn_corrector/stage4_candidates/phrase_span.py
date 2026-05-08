"""Phrase-span proposer — generates safe phrase-span lattice edges.

The :class:`PhraseSpanProposer` scans word islands and produces
:class:`~vn_corrector.stage5_scorer.lattice.LatticeEdge` objects for
every safe phrase match, ready for the Viterbi decoder.
"""

from __future__ import annotations

from vn_corrector.common.lexicon import LexiconStoreInterface
from vn_corrector.stage1_normalize import strip_accents
from vn_corrector.stage4_candidates.word_island import WordIsland
from vn_corrector.stage5_scorer.lattice import (
    LatticeEdge,
    compute_phrase_span_risk,
    compute_phrase_span_score,
    get_phrase_surface,
    is_safe_phrase_restoration,
)


class PhraseSpanProposer:
    """Generate safe phrase-span lattice edges over a ``WordIsland``."""

    def __init__(
        self,
        lexicon: LexiconStoreInterface,
        *,
        min_len: int = 2,
        max_len: int = 8,
    ) -> None:
        self._lexicon = lexicon
        self._min_len = min_len
        self._max_len = max_len

    def propose(self, islands: list[WordIsland]) -> list[LatticeEdge]:
        edges: list[LatticeEdge] = []
        for island in islands:
            edges.extend(self._propose_for_island(island))
        return edges

    def _propose_for_island(self, island: WordIsland) -> list[LatticeEdge]:
        word_tokens = island.word_tokens
        edges: list[LatticeEdge] = []
        n_words = len(word_tokens)

        for i in range(n_words):
            max_j = min(n_words, i + self._max_len)
            for j in range(i + self._min_len, max_j + 1):
                span_tokens = word_tokens[i:j]
                original_span = " ".join(t.text for t in span_tokens)
                no_tone_key = strip_accents(original_span).lower().strip()

                matches = self._lexicon.lookup_phrase_notone(no_tone_key)
                for phrase in matches:
                    if not is_safe_phrase_restoration(original_span, phrase):
                        continue

                    surface = get_phrase_surface(phrase)
                    output_tokens = tuple(surface.split())

                    if len(output_tokens) != (j - i):
                        continue

                    score = compute_phrase_span_score(phrase)
                    risk = compute_phrase_span_risk(phrase, original_span)

                    raw_start = island.raw_token_indexes[i]
                    raw_end = island.raw_token_indexes[j - 1] + 1
                    char_start = span_tokens[0].span.start
                    char_end = span_tokens[-1].span.end

                    edges.append(
                        LatticeEdge(
                            start=i,
                            end=j,
                            output_tokens=output_tokens,
                            score=score,
                            risk=risk,
                            source="phrase_span",
                            raw_start=raw_start,
                            raw_end=raw_end,
                            char_start=char_start,
                            char_end=char_end,
                            phrase=phrase,
                            explanation=(
                                f"phrase-span: {surface} (confidence={phrase.score.confidence:.3f})"
                            ),
                        )
                    )

        return edges
