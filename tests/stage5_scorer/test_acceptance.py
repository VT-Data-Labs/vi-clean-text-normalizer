"""Acceptance tests for the M5 phrase scorer using live phrase data."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from vn_corrector.common.lexicon import (
    LexiconLookupResult,
    LexiconStoreInterface,
    OcrConfusionLookupResult,
)
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

HERE = Path(__file__).resolve().parent
NG_STORE = str(HERE / ".." / ".." / "data" / "processed" / "ngram_store.vi.json")


class FakeLexicon(LexiconStoreInterface):
    """Minimal lexicon for acceptance tests."""

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
        "nước",
        "vào",
        "dụng",
        "cụ",
        "pha",
        "chế",
        "kiểm",
        "tra",
        "nhiệt",
        "độ",
    }

    def contains_word(self, text: str) -> bool:
        return text in self._KNOWN

    def contains_syllable(self, text: str) -> bool:
        return text in self._KNOWN

    def lookup(self, text: str) -> LexiconLookupResult:
        return LexiconLookupResult(query=text, found=False)

    def lookup_accentless(self, text: str) -> LexiconLookupResult:
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


def _make_cand(
    text: str,
    is_original: bool = False,
    edit_dist: int | None = None,
    sources: set[CandidateSource] | None = None,
) -> Candidate:
    if sources is None:
        sources = {CandidateSource.SYLLABLE_MAP}
    evidence: list[CandidateEvidence] = []
    return Candidate(
        text=text,
        normalized=text,
        no_tone_key=text.lower(),
        sources=sources,
        evidence=evidence,
        is_original=is_original,
        edit_distance=edit_dist,
    )


def _make_tc(
    text: str,
    candidates: list[Candidate],
) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=False,
        candidates=candidates,
    )


def _scorer() -> PhraseScorer:
    return PhraseScorer(
        ngram_store=JsonNgramStore(NG_STORE),
        lexicon=FakeLexicon(),
        config=PhraseScorerConfig(),
        weights=ScoringWeights(),
    )


class TestAcceptance:
    def test_muong_correction(self) -> None:
        """số mùông gạt ngang → số muỗng gạt ngang."""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc(
                "mùông",
                [
                    _make_cand("mùông", is_original=True),
                    _make_cand(
                        "muỗng",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                    _make_cand("muông", edit_dist=2),
                ],
            ),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = _scorer().score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "số muỗng gạt ngang"

    def test_lam_nguoi_with_domain(self) -> None:
        """lâm người nhanh → làm nguội nhanh with product_instruction domain."""
        tcs = [
            _make_tc(
                "lâm",
                [
                    _make_cand("lâm", is_original=True),
                    _make_cand(
                        "làm",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                ],
            ),
            _make_tc(
                "người",
                [
                    _make_cand("người", is_original=True),
                    _make_cand(
                        "nguội",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                ],
            ),
            _make_tc("nhanh", [_make_cand("nhanh", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = _scorer().score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "làm nguội nhanh"

    def test_lam_nguoi_without_domain(self) -> None:
        """Should not aggressively correct without domain."""
        tcs = [
            _make_tc(
                "lâm",
                [
                    _make_cand("lâm", is_original=True),
                    _make_cand(
                        "làm",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                ],
            ),
            _make_tc(
                "người",
                [
                    _make_cand("người", is_original=True),
                    _make_cand(
                        "nguội",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                ],
            ),
            _make_tc("nhanh", [_make_cand("nhanh", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = _scorer().score_window(windows[0], domain=None)
        assert result.best is not None
        assert len(result.best.sequence.tokens) > 0

    def test_missing_phrase_no_crash(self) -> None:
        tcs = [
            _make_tc("xyz", [_make_cand("xyz", is_original=True)]),
            _make_tc("abc", [_make_cand("abc", is_original=True)]),
        ]
        windows = build_windows(tcs)
        if windows:
            result = _scorer().score_window(windows[0])
            assert result.best is not None

    def test_explainability(self) -> None:
        """Every changed token must have explanation."""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc(
                "mùông",
                [
                    _make_cand("mùông", is_original=True),
                    _make_cand(
                        "muỗng",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                ],
            ),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = _scorer().score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        for exp in result.best.explanations:
            assert exp.original != exp.corrected
            assert len(exp.evidence) > 0

    def test_relative_ranking(self) -> None:
        """Assert relative ranking, not exact scores."""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc(
                "mùông",
                [
                    _make_cand("mùông", is_original=True),
                    _make_cand(
                        "muỗng",
                        sources={CandidateSource.OCR_CONFUSION},
                        edit_dist=1,
                    ),
                    _make_cand("mường", edit_dist=2),
                ],
            ),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = _scorer().score_window(windows[0], domain="product_instruction")
        scores: dict[str, float] = {}
        for s in result.ranked_sequences:
            scores[" ".join(s.sequence.tokens)] = s.score
        assert scores.get("số muỗng gạt ngang", -999.0) > scores.get("số mường gạt ngang", -999.0)
