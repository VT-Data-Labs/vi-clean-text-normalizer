"""Tests for candidate ranking in Stage 4.

Ensures the ``_sort_key`` tiebreaker uses linguistic signals
(lexicon_freq, evidence count) before falling through to text order.
"""

from __future__ import annotations

from vn_corrector.stage4_candidates import Candidate, CandidateSource
from vn_corrector.stage4_candidates.ranking import rank_candidates
from vn_corrector.stage4_candidates.types import CandidateEvidence

_SOURCE_WEIGHTS: dict[str, float] = {
    "original": 0.10,
    "syllable_map": 0.20,
    "word_lexicon": 0.25,
}


def _candidate(
    text: str,
    lexicon_freq: float = 1.0,
    is_original: bool = False,
    sources: set[CandidateSource] | None = None,
    evidence_count: int = 1,
) -> Candidate:
    if sources is None:
        src = {CandidateSource.ORIGINAL if is_original else CandidateSource.SYLLABLE_MAP}
    else:
        src = sources
    return Candidate(
        text=text,
        normalized=text.lower(),
        no_tone_key=text.lower(),
        sources=src,
        evidence=[CandidateEvidence(source=s, detail="test") for s in src]
        + [CandidateEvidence(source=CandidateSource.WORD_LEXICON, detail="freq_test")]
        * max(0, evidence_count - len(src)),
        is_original=is_original,
        prior_score=0.5,
        lexicon_freq=lexicon_freq,
    )


class TestRankingSortKey:
    def test_frequency_outranks_unicode_order(self) -> None:
        candidates = [
            _candidate("lộng", lexicon_freq=0.1, sources={CandidateSource.WORD_LEXICON}),
            _candidate("lòng", lexicon_freq=0.95, sources={CandidateSource.WORD_LEXICON}),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "lòng", f"Expected 'lòng' first, got {[c.text for c in ranked]}"

    def test_evidence_count_outranks_unicode_order(self) -> None:
        candidates = [
            _candidate(
                "lộng",
                lexicon_freq=1.0,
                sources={CandidateSource.WORD_LEXICON},
                evidence_count=1,
            ),
            _candidate(
                "lòng",
                lexicon_freq=1.0,
                sources={CandidateSource.WORD_LEXICON, CandidateSource.SYLLABLE_MAP},
                evidence_count=2,
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "lòng", (
            f"Expected 'lòng' first (more evidence), got {[c.text for c in ranked]}"
        )

    def test_text_is_last_resort_tiebreaker(self) -> None:
        candidates = [
            _candidate("b", lexicon_freq=1.0, sources={CandidateSource.WORD_LEXICON}),
            _candidate("a", lexicon_freq=1.0, sources={CandidateSource.WORD_LEXICON}),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        texts = [c.text for c in ranked]
        assert texts == ["b", "a"], f"Descending sort should place 'b' before 'a', got {texts}"
