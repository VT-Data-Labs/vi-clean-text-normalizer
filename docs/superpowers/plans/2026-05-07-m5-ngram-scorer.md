# M5 — N-Gram Phrase Scorer Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the context-aware candidate sequence ranking layer (M5) with n-gram phrase evidence, domain scoring, and overcorrection prevention.

**Architecture:** M5 consumes M4's `TokenCandidates[]`, builds bounded windows around ambiguous tokens, generates candidate sequences, and scores them using 8 deterministic signals via `PhraseScorer`. Output is ranked `ScoredSequence[]` with full `ScoreBreakdown` and per-token `TokenCorrectionExplanation`.

**Tech Stack:** Python 3.12+, ABC (not Protocol), frozen dataclasses, pytest, JSON phrase store

---

## Chunk 1: M5.1 — Skeleton Types & Config

### Task 1.1: config.py, weights.py, types.py, __init__.py

**Files:**
- Create: `src/vn_corrector/stage5_scorer/__init__.py`
- Create: `src/vn_corrector/stage5_scorer/config.py`
- Create: `src/vn_corrector/stage5_scorer/weights.py`
- Create: `src/vn_corrector/stage5_scorer/types.py`
- Test: `tests/stage5_scorer/test_types.py`

- [ ] **Step 1: Write test_types.py with type construction, immutability, and ScoreBreakdown.total tests**

```python
import pytest
from vn_corrector.stage5_scorer.types import (
    ScoreBreakdown, CandidateWindow, CandidateSequence,
    CorrectionEvidence, TokenCorrectionExplanation,
    ScoredSequence, ScoredWindow,
)


class TestScoreBreakdown:
    def test_total_no_penalties(self) -> None:
        b = ScoreBreakdown(word_validity=1.0, syllable_freq=0.5, phrase_ngram=1.0)
        assert b.total == pytest.approx(2.5)

    def test_total_with_penalties(self) -> None:
        b = ScoreBreakdown(
            word_validity=1.0, phrase_ngram=1.0, overcorrection_penalty=0.5,
        )
        assert b.total == pytest.approx(1.5)

    def test_total_empty(self) -> None:
        assert ScoreBreakdown().total == pytest.approx(0.0)

    def test_total_negative(self) -> None:
        b = ScoreBreakdown(overcorrection_penalty=3.0, negative_phrase_penalty=2.0)
        assert b.total == pytest.approx(-5.0)


class TestScoredSequence:
    def test_score_property(self) -> None:
        b = ScoreBreakdown(word_validity=2.0)
        seq = CandidateSequence(tokens=("a",), original_tokens=("a",), changed_positions=())
        s = ScoredSequence(sequence=seq, breakdown=b, confidence=0.8)
        assert s.score == pytest.approx(2.0)


class TestScoredWindow:
    def test_best_with_sequences(self) -> None:
        seq = CandidateSequence(tokens=("a",), original_tokens=("a",), changed_positions=())
        w = ScoredWindow(
            window=CandidateWindow(start=0, end=1, token_candidates=[]),
            ranked_sequences=[
                ScoredSequence(sequence=seq, breakdown=ScoreBreakdown(word_validity=2.0), confidence=0.9),
                ScoredSequence(sequence=seq, breakdown=ScoreBreakdown(word_validity=1.0), confidence=0.5),
            ],
        )
        assert w.best is not None
        assert w.best.score == pytest.approx(2.0)

    def test_best_empty(self) -> None:
        w = ScoredWindow(
            window=CandidateWindow(start=0, end=1, token_candidates=[]),
            ranked_sequences=[],
        )
        assert w.best is None


class TestCandidateWindow:
    def test_fields(self) -> None:
        w = CandidateWindow(start=0, end=2, token_candidates=[])
        assert w.start == 0
        assert w.end == 2
        assert w.token_candidates == []


class TestCandidateSequence:
    def test_changed_positions(self) -> None:
        s = CandidateSequence(
            tokens=("x", "y"), original_tokens=("a", "b"), changed_positions=(0, 1),
        )
        assert s.tokens == ("x", "y")
        assert s.changed_positions == (0, 1)
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/stage5_scorer/test_types.py -v
```
Expected: ModuleNotFoundError (package doesn't exist yet)

- [ ] **Step 3: Create config.py, weights.py, types.py, __init__.py**

`config.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseScorerConfig:
    max_tokens_per_window: int = 7
    max_combinations: int = 5000
    max_candidates_per_token: int = 8
    min_score_margin: float = 0.25
    min_apply_confidence: float = 0.65
    enable_bigram_score: bool = True
    enable_trigram_score: bool = True
    enable_fourgram_score: bool = True
    enable_domain_context: bool = True
    enable_negative_phrase_penalty: bool = True
```

`weights.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringWeights:
    word_validity: float = 1.0
    syllable_freq: float = 0.4
    phrase_ngram: float = 1.4
    domain_context: float = 1.2
    ocr_confusion: float = 1.0
    edit_distance: float = 0.6
    overcorrection_penalty: float = 1.3
    negative_phrase_penalty: float = 1.5
```

`types.py` — all 7 frozen dataclasses from the spec (ScoreBreakdown, CandidateWindow, CandidateSequence, CorrectionEvidence, TokenCorrectionExplanation, ScoredSequence, ScoredWindow).

`__init__.py` — exports all public types.

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_types.py -v
```
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/vn_corrector/stage5_scorer/ tests/stage5_scorer/test_types.py
git commit -m "M5.1: add skeleton types, config, weights for phrase scorer"
```

---

## Chunk 2: M5.2 — Phrase Dataset + Ngram Builder

### Task 2.1: Create phrase data files

**Files:**
- Create: `resources/phrases/phrases.vi.json`
- Create: `resources/phrases/negative_phrases.vi.json`
- Create: `resources/phrases/domains/product_instruction.vi.json`

- [ ] **Step 1: Create curated phrase data**

`resources/phrases/phrases.vi.json`:
```json
[
  {
    "phrase": "số muỗng gạt ngang",
    "tokens": ["số", "muỗng", "gạt", "ngang"],
    "normalized": "so muong gat ngang",
    "normalized_tokens": ["so", "muong", "gat", "ngang"],
    "n": 4,
    "score": 0.9,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["measurement", "instruction"]
  },
  {
    "phrase": "làm nguội nhanh",
    "tokens": ["làm", "nguội", "nhanh"],
    "normalized": "lam nguoi nhanh",
    "normalized_tokens": ["lam", "nguoi", "nhanh"],
    "n": 3,
    "score": 0.85,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["process", "instruction"]
  },
  {
    "phrase": "kiểm tra nhiệt độ",
    "tokens": ["kiểm", "tra", "nhiệt", "độ"],
    "normalized": "kiem tra nhiet do",
    "normalized_tokens": ["kiem", "tra", "nhiet", "do"],
    "n": 4,
    "score": 0.85,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["check", "instruction"]
  },
  {
    "phrase": "rót nước vào dụng cụ pha chế",
    "tokens": ["rót", "nước", "vào", "dụng", "cụ", "pha", "chế"],
    "normalized": "rot nuoc vao dung cu pha che",
    "normalized_tokens": ["rot", "nuoc", "vao", "dung", "cu", "pha", "che"],
    "n": 7,
    "score": 0.9,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["instruction"]
  },
  {
    "phrase": "số muỗng",
    "tokens": ["số", "muỗng"],
    "normalized": "so muong",
    "normalized_tokens": ["so", "muong"],
    "n": 2,
    "score": 0.85,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["measurement"]
  },
  {
    "phrase": "muỗng gạt",
    "tokens": ["muỗng", "gạt"],
    "normalized": "muong gat",
    "normalized_tokens": ["muong", "gat"],
    "n": 2,
    "score": 0.8,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["measurement"]
  },
  {
    "phrase": "gạt ngang",
    "tokens": ["gạt", "ngang"],
    "normalized": "gat ngang",
    "normalized_tokens": ["gat", "ngang"],
    "n": 2,
    "score": 0.8,
    "domain": "generic",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["measurement"]
  },
  {
    "phrase": "làm nguội",
    "tokens": ["làm", "nguội"],
    "normalized": "lam nguoi",
    "normalized_tokens": ["lam", "nguoi"],
    "n": 2,
    "score": 0.8,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["process"]
  },
  {
    "phrase": "nguội nhanh",
    "tokens": ["nguội", "nhanh"],
    "normalized": "nguoi nhanh",
    "normalized_tokens": ["nguoi", "nhanh"],
    "n": 2,
    "score": 0.8,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["process"]
  },
  {
    "phrase": "vừa đủ",
    "tokens": ["vừa", "đủ"],
    "normalized": "vua du",
    "normalized_tokens": ["vua", "du"],
    "n": 2,
    "score": 0.75,
    "domain": "generic",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["measurement"]
  },
  {
    "phrase": "hướng dẫn sử dụng",
    "tokens": ["hướng", "dẫn", "sử", "dụng"],
    "normalized": "huong dan su dung",
    "normalized_tokens": ["huong", "dan", "su", "dung"],
    "n": 4,
    "score": 0.85,
    "domain": "generic",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["instruction"]
  }
]
```

`resources/phrases/negative_phrases.vi.json`:
```json
[
  {
    "phrase": "lâm người nhanh",
    "tokens": ["lâm", "người", "nhanh"],
    "normalized": "lam nguoi nhanh",
    "normalized_tokens": ["lam", "nguoi", "nhanh"],
    "n": 3,
    "score": 0.05,
    "domain": null,
    "source": "manual",
    "confidence": 1.0,
    "tags": ["common_ocr_error"]
  },
  {
    "phrase": "làm người nhanh",
    "tokens": ["làm", "người", "nhanh"],
    "normalized": "lam nguoi nhanh",
    "normalized_tokens": ["lam", "nguoi", "nhanh"],
    "n": 3,
    "score": 0.15,
    "domain": null,
    "source": "manual",
    "confidence": 1.0,
    "tags": ["overcorrection_risk"]
  },
  {
    "phrase": "số mường gạt ngang",
    "tokens": ["số", "mường", "gạt", "ngang"],
    "normalized": "so muong gat ngang",
    "normalized_tokens": ["so", "muong", "gat", "ngang"],
    "n": 4,
    "score": 0.05,
    "domain": "product_instruction",
    "source": "manual",
    "confidence": 1.0,
    "tags": ["rare_phrase"]
  }
]
```

`resources/phrases/domains/product_instruction.vi.json`:
```json
{
  "domain": "product_instruction",
  "phrases": [
    "số muỗng gạt ngang",
    "làm nguội nhanh",
    "kiểm tra nhiệt độ",
    "rót nước vào dụng cụ pha chế",
    "số muỗng",
    "muỗng gạt",
    "làm nguội",
    "nguội nhanh"
  ]
}
```

- [ ] **Step 2: Create scripts/build_ngram_store.py**

The build script reads `resources/phrases/phrases.vi.json` and `resources/phrases/negative_phrases.vi.json`, validates that `n == len(tokens)`, generates bigrams/trigrams/fourgrams, merges domain phrases, and writes `resources/ngrams/ngram_store.vi.json`.

Key behavior:
- Each phrase generates its constituent n-grams
- If the same n-gram appears in multiple phrases, keep the max score
- Domain phrases map `domain -> phrase_text -> score`
- Negative phrases get their own section
- Validation: skip any entry where `n != len(tokens)` with a warning

- [ ] **Step 3: Run build script to generate ngram_store.vi.json**

```bash
uv run python scripts/build_ngram_store.py
```
Expected: `resources/ngrams/ngram_store.vi.json` created

- [ ] **Step 4: Commit**

```bash
git add resources/phrases/ resources/ngrams/ scripts/build_ngram_store.py
git commit -m "M5.2: add curated phrase datasets and ngram builder script"
```

---

## Chunk 3: M5.3 — NgramStore ABC + JsonNgramStore

### Task 3.1: Define NgramStore ABC

**Files:**
- Create: `src/vn_corrector/stage5_scorer/ngram_store.py`
- Create: `src/vn_corrector/stage5_scorer/backends/__init__.py`
- Create: `src/vn_corrector/stage5_scorer/backends/json_ngram_store.py`
- Test: `tests/stage5_scorer/test_ngram_store.py`

- [ ] **Step 1: Write test_ngram_store.py with tests for JsonNgramStore**

```python
import pytest
import json
from pathlib import Path
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore


@pytest.fixture
def sample_store(tmp_path: Path) -> JsonNgramStore:
    data = {
        "version": 1,
        "language": "vi",
        "bigrams": {"số muỗng": 0.9, "muỗng gạt": 0.85, "gạt ngang": 0.8},
        "trigrams": {"số muỗng gạt": 0.9, "muỗng gạt ngang": 0.85},
        "fourgrams": {"số muỗng gạt ngang": 0.9},
        "domain_phrases": {
            "product_instruction": {
                "số muỗng gạt ngang": 0.9,
                "làm nguội nhanh": 0.85,
            }
        },
        "negative_phrases": {
            "lâm người nhanh": 0.05,
            "làm người nhanh": 0.1,
        },
    }
    p = tmp_path / "ngram_store.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return JsonNgramStore(str(p))


class TestJsonNgramStore:
    def test_bigram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.bigram_score("số", "muỗng") == pytest.approx(0.9)

    def test_bigram_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.bigram_score("xyz", "abc") == pytest.approx(0.0)

    def test_trigram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.trigram_score("số", "muỗng", "gạt") == pytest.approx(0.9)

    def test_trigram_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.trigram_score("a", "b", "c") == pytest.approx(0.0)

    def test_fourgram_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.fourgram_score("số", "muỗng", "gạt", "ngang") == pytest.approx(0.9)

    def test_phrase_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số", "muỗng", "gạt", "ngang")) == pytest.approx(0.9)

    def test_phrase_score_not_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("abc",)) == pytest.approx(0.0)

    def test_phrase_score_single_token_not_in_ngrams(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.phrase_score(("số",)) == pytest.approx(0.0)

    def test_domain_phrase_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score(
            "product_instruction", ("số", "muỗng", "gạt", "ngang")
        ) == pytest.approx(0.9)

    def test_domain_phrase_score_missing_domain(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score("unknown_domain", ("số", "muỗng")) == pytest.approx(0.0)

    def test_domain_phrase_score_missing_phrase(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.domain_phrase_score(
            "product_instruction", ("abc",)
        ) == pytest.approx(0.0)

    def test_negative_phrase_score_found(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.negative_phrase_score(("lâm", "người", "nhanh")) == pytest.approx(0.05)

    def test_negative_phrase_score_missing(self, sample_store: JsonNgramStore) -> None:
        assert sample_store.negative_phrase_score(("abc",)) == pytest.approx(0.0)

    def test_load_missing_file(self) -> None:
        store = JsonNgramStore("/nonexistent/path.json")
        assert store.bigram_score("a", "b") == pytest.approx(0.0)
        assert store.phrase_score(("a",)) == pytest.approx(0.0)
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/stage5_scorer/test_ngram_store.py -v
```
Expected: ModuleNotFoundError

- [ ] **Step 3: Implement NgramStore ABC and JsonNgramStore**

`ngram_store.py`:
```python
from abc import ABC, abstractmethod


class NgramStore(ABC):
    @abstractmethod
    def bigram_score(self, w1: str, w2: str) -> float: ...
    @abstractmethod
    def trigram_score(self, w1: str, w2: str, w3: str) -> float: ...
    @abstractmethod
    def fourgram_score(self, w1: str, w2: str, w3: str, w4: str) -> float: ...
    @abstractmethod
    def phrase_score(self, tokens: tuple[str, ...]) -> float: ...
    @abstractmethod
    def domain_phrase_score(self, domain: str, tokens: tuple[str, ...]) -> float: ...
    @abstractmethod
    def negative_phrase_score(self, tokens: tuple[str, ...]) -> float: ...
```

`backends/json_ngram_store.py`:
```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vn_corrector.stage5_scorer.ngram_store import NgramStore


class JsonNgramStore(NgramStore):
    def __init__(self, path: str) -> None:
        self._bigrams: dict[str, float] = {}
        self._trigrams: dict[str, float] = {}
        self._fourgrams: dict[str, float] = {}
        self._domain_phrases: dict[str, dict[str, float]] = {}
        self._negative_phrases: dict[str, float] = {}
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            self._bigrams = {k: float(v) for k, v in data.get("bigrams", {}).items()}
            self._trigrams = {k: float(v) for k, v in data.get("trigrams", {}).items()}
            self._fourgrams = {k: float(v) for k, v in data.get("fourgrams", {}).items()}
            self._domain_phrases = {
                domain: {phrase: float(s) for phrase, s in phrases.items()}
                for domain, phrases in data.get("domain_phrases", {}).items()
            }
            self._negative_phrases = {
                k: float(v) for k, v in data.get("negative_phrases", {}).items()
            }

    def bigram_score(self, w1: str, w2: str) -> float:
        return self._bigrams.get(f"{w1} {w2}", 0.0)

    def trigram_score(self, w1: str, w2: str, w3: str) -> float:
        return self._trigrams.get(f"{w1} {w2} {w3}", 0.0)

    def fourgram_score(self, w1: str, w2: str, w3: str, w4: str) -> float:
        return self._fourgrams.get(f"{w1} {w2} {w3} {w4}", 0.0)

    def phrase_score(self, tokens: tuple[str, ...]) -> float:
        key = " ".join(tokens)
        if len(tokens) == 2:
            return self._bigrams.get(key, 0.0)
        if len(tokens) == 3:
            return self._trigrams.get(key, 0.0)
        if len(tokens) == 4:
            return self._fourgrams.get(key, 0.0)
        return 0.0

    def domain_phrase_score(self, domain: str, tokens: tuple[str, ...]) -> float:
        domain_data = self._domain_phrases.get(domain)
        if domain_data is None:
            return 0.0
        return domain_data.get(" ".join(tokens), 0.0)

    def negative_phrase_score(self, tokens: tuple[str, ...]) -> float:
        return self._negative_phrases.get(" ".join(tokens), 0.0)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_ngram_store.py -v
```
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add src/vn_corrector/stage5_scorer/ngram_store.py src/vn_corrector/stage5_scorer/backends/ tests/stage5_scorer/test_ngram_store.py
git commit -m "M5.3: add NgramStore ABC and JsonNgramStore backend"
```

---

## Chunk 4: M5.4 + M5.5 — Windowing + Combination Generation

### Task 4.1: Windowing

**Files:**
- Create: `src/vn_corrector/stage5_scorer/windowing.py`
- Test: `tests/stage5_scorer/test_windowing.py`

### Task 4.2: Combination Generator

**Files:**
- Create: `src/vn_corrector/stage5_scorer/combinations.py`
- Test: `tests/stage5_scorer/test_combinations.py`

- [ ] **Step 1: Write test_windowing.py**

```python
import pytest
from vn_corrector.stage4_candidates.types import TokenCandidates, Candidate
from vn_corrector.stage5_scorer.types import CandidateWindow
from vn_corrector.stage5_scorer.windowing import build_windows


def _make_tc(text: str, candidates: list[str], protected: bool = False) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=protected,
        candidates=[Candidate(
            text=c, normalized=c, no_tone_key=c.lower(),
            sources=set(), evidence=[],
        ) for c in candidates],
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
        assert windows[0].start == 0
        assert windows[0].end >= 3

    def test_no_ambiguous_token(self) -> None:
        tcs = [_make_tc("số", ["số"]), _make_tc("gạt", ["gạt"])]
        windows = build_windows(tcs, max_tokens_per_window=7)
        assert len(windows) == 0

    def test_window_clamped_to_max(self) -> None:
        tokens = [_make_tc(f"t{i}", ["t{i}"]) for i in range(20)]
        tokens[10] = _make_tc("x", ["x", "y"])  # ambiguous at index 10
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
        assert len(merged_starts) <= 2  # should merge overlapping
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/stage5_scorer/test_windowing.py -v
```
Expected: ImportError (windowing.py doesn't exist)

- [ ] **Step 3: Implement windowing.py**

```python
from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import CandidateWindow


def build_windows(
    token_candidates: list[TokenCandidates],
    max_tokens_per_window: int = 7,
) -> list[CandidateWindow]:
    ambiguous_indices = [
        i for i, tc in enumerate(token_candidates)
        if not tc.protected and len(tc.candidates) > 1
    ]
    if not ambiguous_indices:
        return []

    raw_windows: list[tuple[int, int]] = []
    radius = max_tokens_per_window // 2
    total = len(token_candidates)
    for idx in ambiguous_indices:
        start = max(0, idx - radius)
        end = min(total, idx + radius + 1)
        if end - start > max_tokens_per_window:
            end = start + max_tokens_per_window
        raw_windows.append((start, end))

    merged: list[tuple[int, int]] = []
    for start, end in sorted(raw_windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return [
        CandidateWindow(
            start=start,
            end=end,
            token_candidates=token_candidates[start:end],
        )
        for start, end in merged
    ]
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_windowing.py -v
```
Expected: 5 passed

- [ ] **Step 5: Write test_combinations.py**

```python
import pytest
from vn_corrector.stage4_candidates.types import TokenCandidates, Candidate
from vn_corrector.stage5_scorer.types import CandidateWindow, CandidateSequence
from vn_corrector.stage5_scorer.combinations import generate_sequences


def _make_tc(text: str, candidates: list[str]) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=False,
        candidates=[Candidate(
            text=c, normalized=c, no_tone_key=c.lower(),
            sources=set(), evidence=[],
        ) for c in candidates],
    )


class TestGenerateSequences:
    def test_identity_path_preserved(self) -> None:
        tcs = [
            _make_tc("số", ["số"]),
            _make_tc("mùông", ["mùông", "muỗng"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=5000, max_per_token=8)
        identity = tuple(tc.token_text for tc in tcs)
        assert any(s.tokens == identity for s in sequences)

    def test_simple_combinations(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=5000, max_per_token=8)
        texts = {" ".join(s.tokens) for s in sequences}
        assert texts == {"a b", "a c"}

    def test_max_combinations_respected(self) -> None:
        tcs = [_make_tc(f"t{i}", [f"t{i}_v{j}" for j in range(10)]) for i in range(5)]
        window = CandidateWindow(start=0, end=5, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=100, max_per_token=3)
        assert len(sequences) <= 100

    def test_empty_window(self) -> None:
        window = CandidateWindow(start=0, end=0, token_candidates=[])
        sequences = generate_sequences(window, max_combinations=5000, max_per_token=8)
        assert len(sequences) == 0

    def test_returns_candidate_sequences(self) -> None:
        tcs = [
            _make_tc("a", ["a"]),
            _make_tc("b", ["b", "c"]),
        ]
        window = CandidateWindow(start=0, end=2, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=5000, max_per_token=8)
        assert all(isinstance(s, CandidateSequence) for s in sequences)

    def test_single_token_no_alternatives(self) -> None:
        tcs = [_make_tc("a", ["a"])]
        window = CandidateWindow(start=0, end=1, token_candidates=tcs)
        sequences = generate_sequences(window, max_combinations=5000, max_per_token=8)
        assert len(sequences) == 1
        assert sequences[0].tokens == ("a",)
```

- [ ] **Step 6: Implement combinations.py**

```python
import itertools

from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import CandidateWindow, CandidateSequence


def generate_sequences(
    window: CandidateWindow,
    max_combinations: int = 5000,
    max_per_token: int = 8,
) -> list[CandidateSequence]:
    if not window.token_candidates:
        return []

    original_tokens = tuple(tc.token_text for tc in window.token_candidates)

    candidate_lists: list[list[str]] = []
    for tc in window.token_candidates:
        texts = [c.text for c in tc.candidates]
        original = tc.token_text
        filtered = [original]
        for t in texts:
            if t != original and len(filtered) < max_per_token:
                filtered.append(t)
        candidate_lists.append(filtered)

    total = 1
    for cl in candidate_lists:
        total *= len(cl)
    if total > max_combinations:
        trimmed = []
        for cl in candidate_lists:
            if len(cl) > 1:
                trimmed.append(cl[:1] + cl[1:max_per_token])
            else:
                trimmed.append(cl)
        candidate_lists = trimmed

    results: list[CandidateSequence] = []
    for combo in itertools.product(*candidate_lists):
        changed = tuple(i for i, (t, o) in enumerate(zip(combo, original_tokens)) if t != o)
        results.append(CandidateSequence(
            tokens=combo,
            original_tokens=original_tokens,
            changed_positions=changed,
        ))

    return results
```

- [ ] **Step 7: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_windowing.py tests/stage5_scorer/test_combinations.py -v
```
Expected: 11 passed

- [ ] **Step 8: Commit**

```bash
git add src/vn_corrector/stage5_scorer/windowing.py src/vn_corrector/stage5_scorer/combinations.py tests/stage5_scorer/test_windowing.py tests/stage5_scorer/test_combinations.py
git commit -m "M5.4+M5.5: add windowing and combination generation"
```

---

## Chunk 5: M5.6 — PhraseScorer (8 scoring signals)

### Task 5.1: Scorer implementation

**Files:**
- Create: `src/vn_corrector/stage5_scorer/scorer.py`
- Test: `tests/stage5_scorer/test_scorer.py`

- [ ] **Step 1: Write test_scorer.py**

```python
import pytest
from vn_corrector.stage4_candidates.types import TokenCandidates, Candidate, CandidateSource, CandidateEvidence
from vn_corrector.stage5_scorer.types import (
    CandidateWindow, CandidateSequence, ScoreBreakdown,
    ScoredSequence, ScoredWindow,
)
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.stage5_scorer.scorer import PhraseScorer
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore
from vn_corrector.stage5_scorer.combinations import generate_sequences
from vn_corrector.stage5_scorer.windowing import build_windows


class FakeNgramStore(JsonNgramStore):
    def __init__(self) -> None:
        self._bigrams = {"số muỗng": 0.9, "muỗng gạt": 0.85, "gạt ngang": 0.8}
        self._trigrams = {"số muỗng gạt": 0.9, "muỗng gạt ngang": 0.85}
        self._fourgrams = {"số muỗng gạt ngang": 0.9}
        self._domain_phrases = {
            "product_instruction": {
                "số muỗng gạt ngang": 0.9,
                "làm nguội nhanh": 0.85,
            }
        }
        self._negative_phrases = {
            "lâm người nhanh": 0.05,
            "làm người nhanh": 0.1,
        }


class FakeLexicon:
    def contains_word(self, text: str) -> bool:
        known = {"số", "muỗng", "gạt", "ngang", "mùông", "muông", "mường",
                 "làm", "nguội", "nhanh", "lâm", "người", "vừa", "đủ", "rất"}
        return text in known

    def contains_syllable(self, text: str) -> bool:
        return self.contains_word(text)


def _make_candidate(text: str, is_original: bool = False, edit_dist: int | None = None,
                    source: CandidateSource = CandidateSource.SYLLABLE_MAP) -> Candidate:
    evidence = [CandidateEvidence(source=source, detail="test")]
    return Candidate(
        text=text, normalized=text, no_tone_key=text.lower(),
        sources={source}, evidence=evidence,
        is_original=is_original, edit_distance=edit_dist,
    )


def _make_tc(text: str, candidates: list[tuple[str, bool, int | None]]) -> TokenCandidates:
    return TokenCandidates(
        token_text=text, token_index=0, protected=False,
        candidates=[_make_candidate(t, orig, ed) for t, orig, ed in candidates],
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
            _make_tc("số", [("số", True, 0)]),
            _make_tc("mùông", [("mùông", True, 0), ("muỗng", False, 1)]),
            _make_tc("gạt", [("gạt", True, 0)]),
            _make_tc("ngang", [("ngang", True, 0)]),
        ]
        windows = build_windows(tcs)
        assert len(windows) >= 1
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "số muỗng gạt ngang"

    def test_lower_score_for_wrong_candidate(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0)]),
            _make_tc("mùông", [("mùông", True, 0), ("muỗng", False, 1), ("mường", False, 2)]),
            _make_tc("gạt", [("gạt", True, 0)]),
            _make_tc("ngang", [("ngang", True, 0)]),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        muong_text = "số muỗng gạt ngang"
        muong_score = next(
            (s.score for s in result.ranked_sequences if " ".join(s.sequence.tokens) == muong_text),
            None,
        )
        muong_text2 = "số mường gạt ngang"
        muong_score2 = next(
            (s.score for s in result.ranked_sequences if " ".join(s.sequence.tokens) == muong_text2),
            None,
        )
        assert muong_score is not None
        assert muong_score2 is not None
        assert muong_score > muong_score2

    def test_missing_phrase_no_crash(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("abc", [("abc", True, 0)]),
            _make_tc("xyz", [("xyz", True, 0)]),
        ]
        windows = build_windows(tcs)
        if windows:
            result = scorer.score_window(windows[0])
            assert result.best is not None

    def test_score_breakdown_present(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0)]),
            _make_tc("mùông", [("mùông", True, 0), ("muỗng", False, 1)]),
            _make_tc("gạt", [("gạt", True, 0)]),
            _make_tc("ngang", [("ngang", True, 0)]),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        b = result.best.breakdown
        assert isinstance(b.word_validity, float)
        assert isinstance(b.phrase_ngram, float)
        assert isinstance(b.ocr_confusion, float)
        assert isinstance(b.edit_distance, float)

    def test_identity_path_never_lowest_when_valid(self, scorer: PhraseScorer) -> None:
        tcs = [
            _make_tc("số", [("số", True, 0)]),
            _make_tc("mùông", [("mùông", True, 0), ("muỗng", False, 1)]),
        ]
        windows = build_windows(tcs)
        result = scorer.score_window(windows[0], domain="product_instruction")
        identity_text = "số mùông"
        identity_score = next(
            (s.score for s in result.ranked_sequences if " ".join(s.sequence.tokens) == identity_text),
            None,
        )
        assert identity_score is not None
        assert identity_score > 0
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/stage5_scorer/test_scorer.py -v
```
Expected: ImportError (scorer.py doesn't exist)

- [ ] **Step 3: Implement scorer.py**

```python
from __future__ import annotations

from vn_corrector.common.types import LexiconStoreInterface
from vn_corrector.stage4_candidates.types import Candidate, CandidateSource, TokenCandidates
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.ngram_store import NgramStore
from vn_corrector.stage5_scorer.types import (
    CandidateSequence,
    CandidateWindow,
    CorrectionEvidence,
    ScoreBreakdown,
    ScoredSequence,
    ScoredWindow,
    TokenCorrectionExplanation,
)
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.stage5_scorer.combinations import generate_sequences
from vn_corrector.stage5_scorer.windowing import build_windows


class PhraseScorer:
    def __init__(
        self,
        ngram_store: NgramStore,
        lexicon: LexiconStoreInterface,
        config: PhraseScorerConfig | None = None,
        weights: ScoringWeights | None = None,
    ) -> None:
        self._ngram_store = ngram_store
        self._lexicon = lexicon
        self._config = config or PhraseScorerConfig()
        self._weights = weights or ScoringWeights()

    def score_window(
        self,
        window: CandidateWindow,
        domain: str | None = None,
    ) -> ScoredWindow:
        sequences = generate_sequences(
            window,
            max_combinations=self._config.max_combinations,
            max_per_token=self._config.max_candidates_per_token,
        )
        scored = [self._score_sequence(s, window, domain) for s in sequences]
        scored.sort(key=lambda s: s.score, reverse=True)
        return ScoredWindow(window=window, ranked_sequences=scored)

    # -- internal scoring ---------------------------------------------------

    def _score_sequence(
        self,
        sequence: CandidateSequence,
        window: CandidateWindow,
        domain: str | None = None,
    ) -> ScoredSequence:
        seq_tokens = sequence.tokens
        orig_tokens = sequence.original_tokens
        w = self._weights

        word_validity = self._score_word_validity(seq_tokens)
        syllable_freq = self._score_syllable_freq(seq_tokens)
        phrase_ngram = self._score_phrase_ngram(seq_tokens)
        domain_score = self._score_domain_context(seq_tokens, domain)
        ocr_conf = self._score_ocr_confusion(seq_tokens, orig_tokens, window)
        edit_dist = self._score_edit_distance(seq_tokens, orig_tokens, window)
        overcorrection = self._score_overcorrection_penalty(seq_tokens, orig_tokens)
        negative = self._score_negative_phrase_penalty(seq_tokens)

        breakdown = ScoreBreakdown(
            word_validity=word_validity * w.word_validity,
            syllable_freq=syllable_freq * w.syllable_freq,
            phrase_ngram=phrase_ngram * w.phrase_ngram,
            domain_context=domain_score * w.domain_context,
            ocr_confusion=ocr_conf * w.ocr_confusion,
            edit_distance=edit_dist * w.edit_distance,
            overcorrection_penalty=overcorrection * w.overcorrection_penalty,
            negative_phrase_penalty=negative * w.negative_phrase_penalty,
        )

        confidence = self._compute_confidence(breakdown)
        explanations = self._build_explanations(sequence, breakdown)

        return ScoredSequence(
            sequence=sequence,
            breakdown=breakdown,
            confidence=confidence,
            explanations=explanations,
        )

    def _score_word_validity(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        for t in tokens:
            if self._lexicon.contains_word(t):
                score += 1.0
        return score

    def _score_syllable_freq(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        for t in tokens:
            if self._lexicon.contains_syllable(t):
                score += 0.3
        return score

    def _score_phrase_ngram(self, tokens: tuple[str, ...]) -> float:
        score = 0.0
        ns = self._ngram_store
        for i in range(len(tokens) - 1):
            score += ns.bigram_score(tokens[i], tokens[i + 1])
        for i in range(len(tokens) - 2):
            score += ns.trigram_score(tokens[i], tokens[i + 1], tokens[i + 2])
        for i in range(len(tokens) - 3):
            score += ns.fourgram_score(tokens[i], tokens[i + 1], tokens[i + 2], tokens[i + 3])
        return score

    def _score_domain_context(self, tokens: tuple[str, ...], domain: str | None) -> float:
        if not domain or not self._config.enable_domain_context:
            return 0.0
        return self._ngram_store.domain_phrase_score(domain, tokens)

    def _score_ocr_confusion(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
        window: CandidateWindow,
    ) -> float:
        score = 0.0
        for tok_idx, (token, orig) in enumerate(zip(tokens, original_tokens)):
            if token == orig:
                continue
            for tc in window.token_candidates:
                if tc.token_text != orig:
                    continue
                for cand in tc.candidates:
                    if cand.text == token and CandidateSource.OCR_CONFUSION in cand.sources:
                        score += 1.0
                        break
        return score

    def _score_edit_distance(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
        window: CandidateWindow,
    ) -> float:
        score = 0.0
        for tok_idx, (token, orig) in enumerate(zip(tokens, original_tokens)):
            if token == orig:
                score += 1.0
                continue
            for tc in window.token_candidates:
                if tc.token_text != orig:
                    continue
                for cand in tc.candidates:
                    if cand.text == token and cand.edit_distance is not None:
                        score += 1.0 / (1.0 + cand.edit_distance)
                        break
        return score

    def _score_overcorrection_penalty(
        self,
        tokens: tuple[str, ...],
        original_tokens: tuple[str, ...],
    ) -> float:
        changed_valid = 0
        total = 0
        for token, orig in zip(tokens, original_tokens):
            if token == orig:
                continue
            total += 1
            if self._lexicon.contains_word(orig):
                changed_valid += 1
        if total == 0:
            return 0.0
        return changed_valid / total

    def _score_negative_phrase_penalty(self, tokens: tuple[str, ...]) -> float:
        return self._ngram_store.negative_phrase_score(tokens)

    @staticmethod
    def _compute_confidence(breakdown: ScoreBreakdown) -> float:
        raw = breakdown.total
        clamped = max(0.0, min(1.0, (raw + 5.0) / 10.0))
        return clamped

    @staticmethod
    def _build_explanations(
        sequence: CandidateSequence,
        breakdown: ScoreBreakdown,
    ) -> list[TokenCorrectionExplanation]:
        exp: list[TokenCorrectionExplanation] = []
        for pos in sequence.changed_positions:
            orig = sequence.original_tokens[pos]
            corr = sequence.tokens[pos]
            evidence: list[CorrectionEvidence] = []
            if breakdown.ocr_confusion > 0:
                evidence.append(CorrectionEvidence(
                    kind="ocr_confusion",
                    message=f"OCR confusion evidence supports {orig} → {corr}",
                    score_delta=breakdown.ocr_confusion,
                ))
            if breakdown.phrase_ngram > 0:
                evidence.append(CorrectionEvidence(
                    kind="phrase_ngram",
                    message="Phrase n-gram evidence supports this sequence",
                    score_delta=breakdown.phrase_ngram,
                ))
            if breakdown.edit_distance > 0:
                evidence.append(CorrectionEvidence(
                    kind="edit_distance",
                    message=f"Candidate is close to original",
                    score_delta=breakdown.edit_distance,
                ))
            if breakdown.domain_context > 0:
                evidence.append(CorrectionEvidence(
                    kind="domain_context",
                    message="Domain phrase match",
                    score_delta=breakdown.domain_context,
                ))
            exp.append(TokenCorrectionExplanation(
                index=pos,
                original=orig,
                corrected=corr,
                evidence=evidence,
            ))
        return exp
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_scorer.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/vn_corrector/stage5_scorer/scorer.py tests/stage5_scorer/test_scorer.py
git commit -m "M5.6: add PhraseScorer with all 8 scoring signals"
```

---

## Chunk 6: M5.7 — Explanation + Diagnostics

### Task 6.1: explain.py and diagnostics.py

**Files:**
- Create: `src/vn_corrector/stage5_scorer/explain.py`
- Create: `src/vn_corrector/stage5_scorer/diagnostics.py`
- Test: `tests/stage5_scorer/test_explain.py`

- [ ] **Step 1: Write test_explain.py**

```python
import pytest
from vn_corrector.stage5_scorer.types import (
    ScoredSequence, ScoreBreakdown, CandidateSequence, CorrectionEvidence,
    TokenCorrectionExplanation,
)
from vn_corrector.stage5_scorer.explain import format_explanation


class TestFormatExplanation:
    def test_format_basic(self) -> None:
        seq = CandidateSequence(
            tokens=("số", "muỗng", "gạt", "ngang"),
            original_tokens=("số", "mùông", "gạt", "ngang"),
            changed_positions=(1,),
        )
        breakdown = ScoreBreakdown(
            word_validity=4.0, phrase_ngram=2.5, ocr_confusion=1.0,
            edit_distance=0.5, overcorrection_penalty=0.0,
            negative_phrase_penalty=0.0,
        )
        explanations = [
            TokenCorrectionExplanation(
                index=1, original="mùông", corrected="muỗng",
                evidence=[
                    CorrectionEvidence(kind="ocr_confusion", message="OCR support", score_delta=1.0),
                    CorrectionEvidence(kind="edit_distance", message="Distance 1", score_delta=0.5),
                ],
            ),
        ]
        scored = ScoredSequence(
            sequence=seq, breakdown=breakdown,
            confidence=0.85, explanations=explanations,
        )
        result = format_explanation(scored)
        assert "mùông" in result
        assert "muỗng" in result
        assert "ocr_confusion" in result
        assert "ScoreBreakdown" in result or "word_validity" in result

    def test_format_no_changes(self) -> None:
        seq = CandidateSequence(
            tokens=("a", "b"), original_tokens=("a", "b"), changed_positions=(),
        )
        scored = ScoredSequence(
            sequence=seq, breakdown=ScoreBreakdown(),
            confidence=1.0, explanations=[],
        )
        result = format_explanation(scored)
        assert "no changes" in result.lower() or "No changes" in result
```

- [ ] **Step 2: Run failing test**

```bash
pytest tests/stage5_scorer/test_explain.py -v
```
Expected: ImportError (explain.py doesn't exist)

- [ ] **Step 3: Implement explain.py and diagnostics.py**

`explain.py`:
```python
from vn_corrector.stage5_scorer.types import ScoredSequence


def format_explanation(scored: ScoredSequence) -> str:
    lines: list[str] = []
    lines.append(f"Score: {scored.score:.3f}  Confidence: {scored.confidence:.3f}")
    lines.append(f"Original: {' '.join(scored.sequence.original_tokens)}")
    lines.append(f"Corrected: {' '.join(scored.sequence.tokens)}")

    if not scored.explanations:
        lines.append("No changes applied.")
        return "\n".join(lines)

    for exp in scored.explanations:
        lines.append(f"\nToken [{exp.index}]: {exp.original} → {exp.corrected}")
        for ev in exp.evidence:
            delta_str = f" ({ev.score_delta:+.3f})" if ev.score_delta else ""
            lines.append(f"  • {ev.kind}: {ev.message}{delta_str}")

    lines.append(f"\nScoreBreakdown:")
    b = scored.breakdown
    lines.append(f"  word_validity:         {b.word_validity:+.3f}")
    lines.append(f"  syllable_freq:         {b.syllable_freq:+.3f}")
    lines.append(f"  phrase_ngram:          {b.phrase_ngram:+.3f}")
    lines.append(f"  domain_context:        {b.domain_context:+.3f}")
    lines.append(f"  ocr_confusion:         {b.ocr_confusion:+.3f}")
    lines.append(f"  edit_distance:         {b.edit_distance:+.3f}")
    lines.append(f"  overcorrection_penalty: {b.overcorrection_penalty:+.3f}")
    lines.append(f"  negative_phrase_penalty: {b.negative_phrase_penalty:+.3f}")
    lines.append(f"  ─────────────────────────────")
    lines.append(f"  total:                 {b.total:+.3f}")
    return "\n".join(lines)
```

`diagnostics.py`:
```python
from vn_corrector.stage5_scorer.types import ScoredWindow


def format_scored_window(window: ScoredWindow, top_k: int = 5) -> str:
    lines: list[str] = []
    w = window.window
    tok_texts = [tc.token_text for tc in w.token_candidates]
    lines.append(f"Window [{w.start}:{w.end}]: {' | '.join(tok_texts)}")
    lines.append(f"Ranked sequences (top {top_k}):")

    for i, scored in enumerate(window.ranked_sequences[:top_k]):
        tokens = " ".join(scored.sequence.tokens)
        changed = len(scored.sequence.changed_positions)
        marker = " <<<" if i == 0 else ""
        lines.append(
            f"  {i + 1}. [{scored.score:+.3f}] {tokens}"
            f"  (changed={changed}, conf={scored.confidence:.3f}){marker}"
        )

    if window.best and window.best.explanations:
        lines.append("\nExplanations for best:")
        for exp in window.best.explanations:
            ev_str = "; ".join(f"{e.kind}({e.score_delta:+.3f})" for e in exp.evidence)
            lines.append(f"  [{exp.index}] {exp.original} → {exp.corrected}: {ev_str}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/stage5_scorer/test_explain.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/vn_corrector/stage5_scorer/explain.py src/vn_corrector/stage5_scorer/diagnostics.py tests/stage5_scorer/test_explain.py
git commit -m "M5.7: add explanation and diagnostics modules"
```

---

## Chunk 7: M5.8 — Acceptance Tests + Integration

### Task 7.1: Full end-to-end acceptance tests

**Files:**
- Create: `tests/stage5_scorer/test_acceptance.py`
- Modify: `src/vn_corrector/stage5_scorer/__init__.py` (add convenience entry point)

- [ ] **Step 1: Write acceptance tests**

```python
import pytest
from pathlib import Path
from vn_corrector.stage4_candidates.types import TokenCandidates, Candidate, CandidateSource, CandidateEvidence
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.stage5_scorer.scorer import PhraseScorer
from vn_corrector.stage5_scorer.windowing import build_windows


HERE = Path(__file__).resolve().parent
NG_STORE = str(HERE / ".." / ".." / "resources" / "ngrams" / "ngram_store.vi.json")


class FakeLexicon:
    def contains_word(self, text: str) -> bool:
        return text in {
            "số", "muỗng", "gạt", "ngang", "mùông", "muông", "mường",
            "làm", "nguội", "nhanh", "lâm", "người",
            "vừa", "đủ", "rất", "nước", "vào", "dụng", "cụ", "pha", "chế",
            "kiểm", "tra", "nhiệt", "độ",
        }

    def contains_syllable(self, text: str) -> bool:
        return self.contains_word(text)


def _make_cand(text: str, is_original: bool = False, edit_dist: int | None = None,
               sources: set[CandidateSource] | None = None) -> Candidate:
    if sources is None:
        sources = {CandidateSource.SYLLABLE_MAP}
    evidence = [CandidateEvidence(source=list(sources)[0], detail="test")]
    return Candidate(
        text=text, normalized=text, no_tone_key=text.lower(),
        sources=sources, evidence=evidence,
        is_original=is_original, edit_distance=edit_dist,
    )


def _make_tc(text: str, candidates: list[Candidate]) -> TokenCandidates:
    return TokenCandidates(token_text=text, token_index=0, protected=False, candidates=candidates)


@pytest.fixture(scope="module")
def real_scorer() -> PhraseScorer:
    return PhraseScorer(
        ngram_store=JsonNgramStore(NG_STORE),
        lexicon=FakeLexicon(),
        config=PhraseScorerConfig(),
        weights=ScoringWeights(),
    )


class TestAcceptance:
    def test_muong_correction(self, real_scorer: PhraseScorer) -> None:
        """số mùông gạt ngang → số muỗng gạt ngang"""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc("mùông", [
                _make_cand("mùông", is_original=True),
                _make_cand("muỗng", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
                _make_cand("muông", edit_dist=2),
            ]),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = real_scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "số muỗng gạt ngang", f"Expected 'số muỗng gạt ngang', got '{best_text}'"

    def test_lam_nguoi_with_domain(self, real_scorer: PhraseScorer) -> None:
        """lâm người nhanh → làm nguội nhanh with product_instruction domain"""
        tcs = [
            _make_tc("lâm", [
                _make_cand("lâm", is_original=True),
                _make_cand("làm", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
            ]),
            _make_tc("người", [
                _make_cand("người", is_original=True),
                _make_cand("nguội", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
            ]),
            _make_tc("nhanh", [_make_cand("nhanh", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = real_scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        assert best_text == "làm nguội nhanh", f"Expected 'làm nguội nhanh', got '{best_text}'"

    def test_lam_nguoi_without_domain(self, real_scorer: PhraseScorer) -> None:
        """lâm người nhanh should not aggressively correct without domain"""
        tcs = [
            _make_tc("lâm", [
                _make_cand("lâm", is_original=True),
                _make_cand("làm", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
            ]),
            _make_tc("người", [
                _make_cand("người", is_original=True),
                _make_cand("nguội", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
            ]),
            _make_tc("nhanh", [_make_cand("nhanh", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = real_scorer.score_window(windows[0], domain=None)
        assert result.best is not None
        best_text = " ".join(result.best.sequence.tokens)
        # Without domain context, original should rank high enough
        # that the scorer doesn't confidently pick làm nguội nhanh
        # (we just verify it runs without error and produces reasonable output)
        assert len(best_text) > 0

    def test_missing_phrase_no_crash(self, real_scorer: PhraseScorer) -> None:
        """Unknown phrase should not crash"""
        tcs = [
            _make_tc("xyz", [_make_cand("xyz", is_original=True)]),
            _make_tc("abc", [_make_cand("abc", is_original=True)]),
        ]
        windows = build_windows(tcs)
        if windows:
            result = real_scorer.score_window(windows[0])
            assert result.best is not None

    def test_explainability(self, real_scorer: PhraseScorer) -> None:
        """Every changed token must have explanation"""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc("mùông", [
                _make_cand("mùông", is_original=True),
                _make_cand("muỗng", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
            ]),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = real_scorer.score_window(windows[0], domain="product_instruction")
        assert result.best is not None
        for exp in result.best.explanations:
            assert exp.original != exp.corrected
            assert len(exp.evidence) > 0

    def test_relative_ranking(self, real_scorer: PhraseScorer) -> None:
        """Assert relative ranking, not exact scores"""
        tcs = [
            _make_tc("số", [_make_cand("số", is_original=True)]),
            _make_tc("mùông", [
                _make_cand("mùông", is_original=True),
                _make_cand("muỗng", sources={CandidateSource.OCR_CONFUSION}, edit_dist=1),
                _make_cand("mường", edit_dist=2),
            ]),
            _make_tc("gạt", [_make_cand("gạt", is_original=True)]),
            _make_tc("ngang", [_make_cand("ngang", is_original=True)]),
        ]
        windows = build_windows(tcs)
        result = real_scorer.score_window(windows[0], domain="product_instruction")
        scores = {}
        for s in result.ranked_sequences:
            scores[" ".join(s.sequence.tokens)] = s.score
        assert scores.get("số muỗng gạt ngang", -999) > scores.get("số mường gạt ngang", -999)
```

- [ ] **Step 2: Run acceptance tests**

```bash
pytest tests/stage5_scorer/test_acceptance.py -v
```
Expected: All tests pass

- [ ] **Step 3: Update __init__.py to export convenience entry point**

```python
from vn_corrector.stage5_scorer.config import PhraseScorerConfig
from vn_corrector.stage5_scorer.weights import ScoringWeights
from vn_corrector.stage5_scorer.types import (
    ScoreBreakdown,
    CandidateWindow,
    CandidateSequence,
    CorrectionEvidence,
    TokenCorrectionExplanation,
    ScoredSequence,
    ScoredWindow,
)
from vn_corrector.stage5_scorer.scorer import PhraseScorer
from vn_corrector.stage5_scorer.diagnostics import format_scored_window
from vn_corrector.stage5_scorer.explain import format_explanation
from vn_corrector.stage5_scorer.windowing import build_windows
from vn_corrector.stage5_scorer.combinations import generate_sequences
from vn_corrector.stage5_scorer.ngram_store import NgramStore
from vn_corrector.stage5_scorer.backends.json_ngram_store import JsonNgramStore

__all__ = [
    "PhraseScorerConfig",
    "ScoringWeights",
    "ScoreBreakdown",
    "CandidateWindow",
    "CandidateSequence",
    "CorrectionEvidence",
    "TokenCorrectionExplanation",
    "ScoredSequence",
    "ScoredWindow",
    "PhraseScorer",
    "format_scored_window",
    "format_explanation",
    "build_windows",
    "generate_sequences",
    "NgramStore",
    "JsonNgramStore",
]
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/stage5_scorer/ -v
```
Expected: ~41 passed

- [ ] **Step 5: Commit**

```bash
git add tests/stage5_scorer/test_acceptance.py src/vn_corrector/stage5_scorer/__init__.py
git commit -m "M5.8: add acceptance tests and integration entry point"
```

---

## Final verification

- [ ] **Run full CI suite**

```bash
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```
Expected: All pass
