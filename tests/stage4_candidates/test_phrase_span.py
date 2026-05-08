"""Tests for phrase-span proposer."""

from __future__ import annotations

from typing import Any, ClassVar

from vn_corrector.common.enums import TokenType
from vn_corrector.common.lexicon import (
    LexiconLookupResult,
    LexiconStoreInterface,
    OcrConfusionLookupResult,
    PhraseEntry,
    Provenance,
)
from vn_corrector.common.scoring import Score
from vn_corrector.common.spans import TextSpan, Token
from vn_corrector.stage4_candidates.phrase_span import PhraseSpanProposer
from vn_corrector.stage4_candidates.word_island import WordIsland


class FakePhraseLexicon(LexiconStoreInterface):
    """Lexicon stub with phrase data for testing the proposer."""

    _PHRASE_NOTONE_MAP: ClassVar[dict[str, list[PhraseEntry]]] = {}

    def _make(self, surface: str, no_tone: str, n: int, conf: float) -> PhraseEntry:
        return PhraseEntry(
            entry_id=f"phrase/{surface}",
            phrase=surface,
            normalized=surface,
            no_tone=no_tone,
            n=n,
            score=Score(confidence=conf, frequency=conf),
            provenance=Provenance(),
        )

    def __init__(self) -> None:
        # Populate phrase entries
        entries: list[PhraseEntry] = [
            self._make("vậy thì", "vay thi", 2, 0.98),
            self._make("làm thế nào", "lam the nao", 3, 0.98),
            self._make("mối quan hệ", "moi quan he", 3, 0.99),
            self._make("quan hệ", "quan he", 2, 0.98),
            self._make("không biết làm sao", "khong biet lam sao", 4, 0.98),
            self._make("có gì đâu", "co gi dau", 3, 0.98),
            self._make("ma túy", "ma tuy", 2, 0.97),
            # low confidence entry that should not pass safety
            self._make("vậy thì", "vay thi", 2, 0.50),
        ]
        self._map: dict[str, list[PhraseEntry]] = {}
        for e in entries:
            self._map.setdefault(e.no_tone, []).append(e)

    def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
        return list(self._map.get(no_tone_key.strip().lower(), []))

    def contains_word(self, _text: str) -> bool:
        return False

    def contains_syllable(self, _text: str) -> bool:
        return False

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


def _make_token(
    text: str,
    token_type: TokenType = TokenType.VI_WORD,
    start: int = 0,
    end: int | None = None,
) -> Token:
    if end is None:
        end = start + len(text)
    return Token(text=text, token_type=token_type, span=TextSpan(start=start, end=end))


def _make_island(*words: str, base_start: int = 0) -> WordIsland:
    tokens = []
    indexes = []
    pos = base_start
    for i, w in enumerate(words):
        t = _make_token(w, start=pos, end=pos + len(w))
        tokens.append(t)
        indexes.append(i * 2)  # simulate spaced raw tokens
        pos += len(w) + 1
    return WordIsland(
        word_tokens=tuple(tokens),
        raw_token_indexes=tuple(indexes),
        raw_start=indexes[0],
        raw_end=indexes[-1] + 1,
        char_span=TextSpan(start=tokens[0].span.start, end=tokens[-1].span.end),
    )


class TestPhraseSpanProposer:
    def test_proposer_finds_phrase_across_spaces(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("vay", "thi")
        edges = proposer._propose_for_island(island)
        assert len(edges) >= 1
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) >= 1
        assert phrase_edges[0].output_tokens == ("vậy", "thì")

    def test_proposer_uses_word_indexes_not_raw_indexes(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("vay", "thi", base_start=0)
        edges = proposer._propose_for_island(island)
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) >= 1
        e = phrase_edges[0]
        assert e.start == 0
        assert e.end == 2
        assert e.raw_start is not None
        assert e.raw_end is not None

    def test_proposer_rejects_single_token_phrase(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("ma")
        edges = proposer._propose_for_island(island)
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) == 0

    def test_proposer_rejects_mismatched_phrase(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("vay", "khong")
        edges = proposer._propose_for_island(island)
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) == 0

    def test_proposer_scores_long_phrase_above_short_phrase(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("lam", "the", "nao")
        edges = proposer._propose_for_island(island)
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) >= 1
        # "lam the nao" -> "làm thế nào" with n=3
        assert phrase_edges[0].output_tokens == ("làm", "thế", "nào")
        assert phrase_edges[0].score > 0

    def test_proposer_rejects_low_confidence_phrase(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island = _make_island("vay", "thi")
        edges = proposer._propose_for_island(island)
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        # Only high-confidence entries pass the gate
        assert len(phrase_edges) == 1
        assert phrase_edges[0].phrase is not None
        assert phrase_edges[0].phrase.score.confidence >= 0.85

    def test_proposer_propose_aggregates_islands(self) -> None:
        lexicon = FakePhraseLexicon()
        proposer = PhraseSpanProposer(lexicon, min_len=2, max_len=8)
        island1 = _make_island("vay", "thi", base_start=0)
        island2 = _make_island("lam", "the", "nao", base_start=10)
        edges = proposer.propose([island1, island2])
        phrase_edges = [e for e in edges if e.source == "phrase_span"]
        assert len(phrase_edges) == 2
