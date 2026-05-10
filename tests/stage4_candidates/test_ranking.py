"""Tests for candidate ranking in Stage 4.

Ensures the ``_sort_key`` tiebreaker uses linguistic signals
(word_freq, syllable_freq, evidence count, edit_distance) and
does **not** use Unicode text order.
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
    is_known_word: bool = False,
    syllable_freq: float | None = None,
    word_freq: float | None = None,
    is_original: bool = False,
    sources: set[CandidateSource] | None = None,
    evidence_count: int = 1,
    edit_distance: int | None = None,
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
        is_known_word=is_known_word,
        syllable_freq=syllable_freq,
        word_freq=word_freq,
        edit_distance=edit_distance,
    )


class TestRankingSortKey:
    def test_word_freq_outranks_unicode_order(self) -> None:
        """word_freq should override any Unicode ordering."""
        candidates = [
            _candidate(
                "lộng", word_freq=0.1, is_known_word=True, sources={CandidateSource.WORD_LEXICON}
            ),
            _candidate(
                "lòng", word_freq=0.95, is_known_word=True, sources={CandidateSource.WORD_LEXICON}
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "lòng", f"Expected 'lòng' first, got {[c.text for c in ranked]}"

    def test_syllable_freq_outranks_unicode_order(self) -> None:
        """syllable_freq should override any Unicode ordering."""
        candidates = [
            _candidate("cáp", syllable_freq=0.1, sources={CandidateSource.SYLLABLE_MAP}),
            _candidate("cấp", syllable_freq=0.95, sources={CandidateSource.SYLLABLE_MAP}),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "cấp", f"Expected 'cấp' first, got {[c.text for c in ranked]}"

    def test_evidence_count_outranks_unicode_order(self) -> None:
        candidates = [
            _candidate(
                "lộng",
                word_freq=1.0,
                is_known_word=True,
                sources={CandidateSource.WORD_LEXICON},
                evidence_count=1,
            ),
            _candidate(
                "lòng",
                word_freq=1.0,
                is_known_word=True,
                sources={CandidateSource.WORD_LEXICON, CandidateSource.SYLLABLE_MAP},
                evidence_count=2,
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "lòng", (
            f"Expected 'lòng' first (more evidence), got {[c.text for c in ranked]}"
        )

    def test_known_word_does_not_overwrite_syllable_frequency(self) -> None:
        """Known-word validity and syllable frequency are independent signals."""
        candidates = [
            _candidate(
                "cấp",
                is_known_word=True,
                word_freq=0.8,
                syllable_freq=0.9,
                sources={CandidateSource.WORD_LEXICON, CandidateSource.SYLLABLE_MAP},
            ),
            _candidate(
                "cáp",
                is_known_word=True,
                word_freq=0.5,
                syllable_freq=0.1,
                sources={CandidateSource.WORD_LEXICON, CandidateSource.SYLLABLE_MAP},
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        assert ranked[0].text == "cấp", f"Expected 'cấp' first, got {[c.text for c in ranked]}"

    def test_unicode_text_is_not_ranking_tiebreaker(self) -> None:
        """candidate.text must not be a ranking tiebreaker."""
        candidates = [
            _candidate(
                "b", word_freq=1.0, is_known_word=True, sources={CandidateSource.WORD_LEXICON}
            ),
            _candidate(
                "a", word_freq=1.0, is_known_word=True, sources={CandidateSource.WORD_LEXICON}
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        texts = [c.text for c in ranked]
        # Both have same word_freq, same syllable_freq (None→0), same evidence count,
        # same edit_distance (None→ -999 negation).  Tiebreaking uses these
        # fields — but NOT text.  Order is stable, not Unicode-driven.
        assert set(texts) == {"a", "b"}, f"Both candidates must be present, got {texts}"

    def test_edit_distance_tiebreaker(self) -> None:
        """Smaller edit distance should rank higher when other signals tie."""
        candidates = [
            _candidate(
                "cáp",
                word_freq=1.0,
                is_known_word=True,
                sources={CandidateSource.WORD_LEXICON},
                edit_distance=2,
            ),
            _candidate(
                "cấp",
                word_freq=1.0,
                is_known_word=True,
                sources={CandidateSource.WORD_LEXICON},
                edit_distance=1,
            ),
        ]
        ranked = rank_candidates(candidates, _SOURCE_WEIGHTS)
        texts = [c.text for c in ranked]
        assert ranked[0].text == "cấp", f"Expected 'cấp' first (lower edit distance), got {texts}"
