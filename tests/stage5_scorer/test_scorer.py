"""Tests for the PhraseScorer."""

from __future__ import annotations

from typing import Any, ClassVar

import pytest

from vn_corrector.common.lexicon import (
    LexiconEntry,
    LexiconLookupResult,
    LexiconStoreInterface,
    OcrConfusionLookupResult,
)
from vn_corrector.common.scoring import Score
from vn_corrector.stage4_candidates.types import (
    Candidate,
    CandidateEvidence,
    CandidateSource,
    TokenCandidates,
)
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.scorer import PhraseScorer
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.stage5_scorer.windowing import build_windows


class FakeLexicon(LexiconStoreInterface):
    """Minimal lexicon stub for testing."""

    _KNOWN: ClassVar[set[str]] = {
        "số",
        "muỗng",
        "gạt",
        "ngang",
        "mùông",
        "muông",
        "mường",
        "làm",
        "nguội",
        "nhanh",
        "lâm",
        "người",
        "vừa",
        "đủ",
        "nếu",
        "độ",
        "ấm",
        "điện",
        "thoại",
        "thoái",
        "diện",
        "liên",
        "liền",
        "hệ",
        "hè",
        "chính",
        "chủ",
        "he",
        "mối",
        "quan",
        "quân",
        "quận",
    }

    _NO_TONE_MAP: ClassVar[dict[str, list[str]]] = {
        "he": ["he", "hệ", "hè"],
        "dien": ["dien", "điện", "diện"],
        "thoai": ["thoai", "thoại", "thoái"],
        "lien": ["lien", "liên", "liền"],
        "moi": ["moi", "mối", "mọi"],
        "quan": ["quan", "quân", "quận"],
    }

    def contains_word(self, text: str) -> bool:
        return text in self._KNOWN

    def contains_syllable(self, text: str) -> bool:
        return text in self._KNOWN

    def lookup(self, text: str) -> LexiconLookupResult:
        return LexiconLookupResult(query=text, found=False)

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
        surfaces = self._NO_TONE_MAP.get(text.lower(), [])
        if surfaces:
            entries = tuple(
                LexiconEntry(
                    entry_id=f"syllable/{s}",
                    surface=s,
                    normalized=s,
                    no_tone=text.lower(),
                    score=Score(confidence=0.5),
                )
                for s in surfaces
            )
            return LexiconLookupResult(query=text, found=True, entries=entries)
        return LexiconLookupResult(query=text, found=False)

    def lookup_abbreviation(self, text: str) -> LexiconLookupResult:
        return LexiconLookupResult(query=text, found=False)

    def lookup_phrase(self, _text: str) -> list[Any]:
        return []

    def lookup_phrase_str(self, _text: str) -> str | None:
        return None

    def lookup_phrase_normalized(self, _text: str) -> list[Any]:
        return []

    def lookup_ocr(self, _text: str) -> list[str]:
        return []

    def get_ocr_corrections(self, _text: str) -> OcrConfusionLookupResult:
        return OcrConfusionLookupResult(query=_text, found=False)

    def get_syllable_candidates(self, _no_tone_key: str) -> list[Any]:
        return []

    def is_protected_token(self, _text: str) -> bool:
        return False


class FakeNgramStore(JsonNgramStore):
    """In-memory n-gram store for tests."""

    def __init__(self) -> None:
        self._bigrams = {
            "số muỗng": 0.9,
            "muỗng gạt": 0.85,
            "gạt ngang": 0.8,
            "điện thoại": 0.98,
            "thoại liên": 0.85,
            "liên hệ": 0.98,
            "chính chủ": 0.95,
        }
        self._trigrams = {
            "số muỗng gạt": 0.9,
            "muỗng gạt ngang": 0.85,
            "điện thoại liên": 0.85,
            "thoại liên hệ": 0.85,
        }
        self._fourgrams = {"số muỗng gạt ngang": 0.9}
        self._domain_phrases = {
            "product_instruction": {
                "số muỗng gạt ngang": 0.9,
                "làm nguội nhanh": 0.85,
            },
        }
        self._negative_phrases = {
            "lâm người nhanh": 0.05,
            "làm người nhanh": 0.1,
        }


def _make_candidate(
    text: str,
    is_original: bool = False,
    edit_dist: int | None = None,
    source: CandidateSource = CandidateSource.SYLLABLE_MAP,
) -> Candidate:
    evidence: list[CandidateEvidence] = []
    return Candidate(
        text=text,
        normalized=text,
        no_tone_key=text.lower(),
        sources={source},
        evidence=evidence,
        is_original=is_original,
        edit_distance=edit_dist,
    )


def _make_tc(
    text: str,
    candidates: list[tuple[str, bool, int | None, CandidateSource]],
) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=False,
        candidates=[_make_candidate(t, orig, ed, src) for t, orig, ed, src in candidates],
    )


@pytest.fixture
def scorer() -> PhraseScorer:
    return PhraseScorer(
        ngram_store=FakeNgramStore(),
        lexicon=FakeLexicon(),
        config=PhraseScorerConfig(),
        weights=ScoringWeights(),
    )


class TestPhraseScorer:
    def test_best_sequence_chosen(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc(
                "mùông",
                [
                    ("mùông", True, 0, CandidateSource.ORIGINAL),
                    (
                        "muỗng",
                        False,
                        1,
                        CandidateSource.OCR_CONFUSION,
                    ),
                ],
            ),
            _make_tc("gạt", [("gạt", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc("ngang", [("ngang", True, 0, CandidateSource.ORIGINAL)]),
        ]
        windows = build_windows(tcs)
        assert len(windows) >= 1
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "số muỗng gạt ngang"

    def test_lower_score_for_wrong_candidate(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc(
                "mùông",
                [
                    ("mùông", True, 0, CandidateSource.ORIGINAL),
                    (
                        "muỗng",
                        False,
                        1,
                        CandidateSource.OCR_CONFUSION,
                    ),
                    ("mường", False, 2, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc("gạt", [("gạt", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc("ngang", [("ngang", True, 0, CandidateSource.ORIGINAL)]),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        muong = "số muỗng gạt ngang"
        muong_score = next(
            (s.score for s in result.ranked_sequences if " ".join(s.sequence.tokens) == muong),
            None,
        )
        muong2 = "số mường gạt ngang"
        muong_score2 = next(
            (s.score for s in result.ranked_sequences if " ".join(s.sequence.tokens) == muong2),
            None,
        )
        assert muong_score is not None
        assert muong_score2 is not None
        assert muong_score > muong_score2

    def test_missing_phrase_no_crash(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc(
                "abc",
                [("abc", True, 0, CandidateSource.ORIGINAL)],
            ),
            _make_tc(
                "xyz",
                [("xyz", True, 0, CandidateSource.ORIGINAL)],
            ),
        ]
        windows = build_windows(tcs)
        if windows:
            result = scorer.score_window(windows[0])
            assert result.best is not None

    def test_score_breakdown_present(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc(
                "mùông",
                [
                    ("mùông", True, 0, CandidateSource.ORIGINAL),
                    (
                        "muỗng",
                        False,
                        1,
                        CandidateSource.OCR_CONFUSION,
                    ),
                ],
            ),
            _make_tc("gạt", [("gạt", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc("ngang", [("ngang", True, 0, CandidateSource.ORIGINAL)]),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        b = result.best.breakdown
        assert isinstance(b.word_validity, float)
        assert isinstance(b.phrase_ngram, float)
        assert isinstance(b.ocr_confusion, float)
        assert isinstance(b.edit_distance, float)

    def test_identity_path_scored(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0, CandidateSource.ORIGINAL)]),
            _make_tc(
                "mùông",
                [
                    ("mùông", True, 0, CandidateSource.ORIGINAL),
                    (
                        "muỗng",
                        False,
                        1,
                        CandidateSource.OCR_CONFUSION,
                    ),
                ],
            ),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        identity_text = "số mùông"
        identity_score = next(
            (
                s.score
                for s in result.ranked_sequences
                if " ".join(s.sequence.tokens) == identity_text
            ),
            None,
        )
        assert identity_score is not None
        assert identity_score >= 0

    def test_accentless_recovery_with_edit_distance(self, scorer: PhraseScorer) -> None:
        """Corrected accentless phrase outranks identity when edit_distance is set.

        Without edit_distance, identity (all spaces unchanged) wins by a large
        margin. With edit_distance=1 for diacritic-restored tokens, the corrected
        sequence should overtake identity.
        """
        tcs = [
            _make_tc(
                "neu",
                [
                    ("neu", True, 0, CandidateSource.ORIGINAL),
                    ("nếu", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("nều", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "do",
                [
                    ("do", True, 0, CandidateSource.ORIGINAL),
                    ("độ", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("đợ", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "am",
                [
                    ("am", True, 0, CandidateSource.ORIGINAL),
                    ("ấm", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("ậm", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "vua",
                [
                    ("vua", True, 0, CandidateSource.ORIGINAL),
                    ("vừa", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "du",
                [
                    ("du", True, 0, CandidateSource.ORIGINAL),
                    ("đủ", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("đụ", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
        ]
        windows = build_windows(tcs)
        assert len(windows) >= 1
        result = scorer.score_window(windows[0])

        corrected_seq = "nếu độ ấm vừa đủ"
        identity_seq = "neu do am vua du"

        scores = {" ".join(s.sequence.tokens): s.score for s in result.ranked_sequences}

        assert corrected_seq in scores, (
            f"Corrected sequence not found in scored sequences. Available: {list(scores.keys())}"
        )
        assert identity_seq in scores, "Identity sequence not found"

        assert scores[corrected_seq] > scores[identity_seq], (
            f"Corrected (score={scores[corrected_seq]:.4f}) should outrank "
            f"identity (score={scores[identity_seq]:.4f})"
            " when edit_distance is set for diacritic-restored tokens"
        )

    def test_dien_thoai_lien_he_preferred(self, scorer: PhraseScorer) -> None:
        """Accentless "dien thoai lien he" should prefer the correct
        accent-restored sequence over unnatural alternatives.
        """
        tcs = [
            _make_tc(
                "dien",
                [
                    ("dien", True, 0, CandidateSource.ORIGINAL),
                    ("điện", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("diện", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "thoai",
                [
                    ("thoai", True, 0, CandidateSource.ORIGINAL),
                    ("thoại", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("thoái", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "lien",
                [
                    ("lien", True, 0, CandidateSource.ORIGINAL),
                    ("liên", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("liền", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
            _make_tc(
                "he",
                [
                    ("he", True, 0, CandidateSource.ORIGINAL),
                    ("hệ", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("hè", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0])
        correct = "điện thoại liên hệ"
        wrong = "diện thoái liền hệ"
        scores = {" ".join(s.sequence.tokens): s.score for s in result.ranked_sequences}
        assert correct in scores, f"Correct sequence not in scored: {list(scores.keys())}"
        assert wrong in scores, f"Wrong sequence not in scored: {list(scores.keys())}"
        assert scores[correct] > scores[wrong], (
            f"Correct ({correct}: {scores[correct]:.4f}) should outrank "
            f"wrong ({wrong}: {scores[wrong]:.4f})"
        )

    def test_accentless_variant_not_penalized(self, scorer: PhraseScorer) -> None:
        """Accentless→accented corrections should not incur overcorrection penalty.

        "he" is a known word in the lexicon, but since it's a bare no-tone
        form with accented alternatives, changing it to "hệ" should be
        penalty-free.
        """
        tcs = [
            _make_tc(
                "he",
                [
                    ("he", True, 0, CandidateSource.ORIGINAL),
                    ("hệ", False, 1, CandidateSource.SYLLABLE_MAP),
                    ("hè", False, 1, CandidateSource.SYLLABLE_MAP),
                ],
            ),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0])
        corrected_text = "hệ"
        corrected_seq = next(
            s for s in result.ranked_sequences if " ".join(s.sequence.tokens) == corrected_text
        )
        assert corrected_seq.breakdown.overcorrection_penalty == 0.0, (
            f"Expected 0.0 overcorrection penalty for accentless→accented "
            f"correction, got {corrected_seq.breakdown.overcorrection_penalty}"
        )
