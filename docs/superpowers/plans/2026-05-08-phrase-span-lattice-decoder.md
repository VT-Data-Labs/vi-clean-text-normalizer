# M6.1: Phrase-Span Lattice Decoder Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a phrase-span lattice decoder that reliably restores multiple adjacent accentless tokens using safe no-tone phrase lookup and Viterbi decoding.

**Architecture:** Three new components — (1) no-tone phrase index in LexiconDataStore, (2) PhraseSpanProposer that scans token windows and generates phrase-span edges, (3) LatticeDecoder that runs Viterbi over identity/candidate/phrase edges. Wired into the pipeline after candidate generation.

**Tech Stack:** Python 3.12+, SQLite-backed lexicon (data_store.py), existing CandidateGenerator/PhraseScorer pipeline.

---

## Files

| File | Action | Responsibility |
|------|--------|----------------|
| `src/vn_corrector/common/lexicon.py` | Modify | Add `lookup_phrase_notone()` to `LexiconStoreInterface` |
| `src/vn_corrector/stage2_lexicon/backends/data_store.py` | Modify | Add `_notone_phrase_index`, populate from SQLite, implement `lookup_phrase_notone()` |
| `src/vn_corrector/stage4_candidates/phrase_span.py` | Create | `PhraseSpanProposer` that generates phrase-span edges from token windows |
| `src/vn_corrector/stage5_scorer/lattice.py` | Create | `LatticeEdge`, `LatticeDecoder` (Viterbi), safety gates |
| `src/vn_corrector/pipeline/corrector.py` | Modify | Wire phrase-spans into pipeline: generate → decode → merge |
| `tests/stage4_candidates/test_phrase_span.py` | Create | Tests for phrase-span proposer |
| `tests/stage5_scorer/test_lattice.py` | Create | Tests for lattice decoder + safety gates |
| `tests/stage5_scorer/test_acceptance.py` | Modify | Add M6.1 acceptance tests |

---

## Chunk 1: No-Tone Phrase Index

### Task 1.1: Add `lookup_phrase_notone` to interface

**Files:**
- Modify: `src/vn_corrector/common/lexicon.py:189-216`
- Test: not yet (interface change)

- [ ] **Add method to `LexiconStoreInterface`**

In `LexiconStoreInterface` (after `lookup_phrase_normalized`), add:
```python
@abstractmethod
def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]: ...
```

- [ ] **Commit**

```bash
git add src/vn_corrector/common/lexicon.py
git commit -m "feat: add lookup_phrase_notone to LexiconStoreInterface"
```

### Task 1.2: Add `lookup_phrase_notone` to `LexiconDataStore`

**Files:**
- Modify: `src/vn_corrector/stage2_lexicon/backends/data_store.py`
- Test: `tests/stage5_scorer/test_acceptance.py`

- [ ] **Add `_notone_phrase_index` to `__init__`**

In `LexiconDataStore.__init__`, add:
```python
self._notone_phrase_index: dict[str, list[PhraseEntry]] = {}
```

- [ ] **Populate index in `load_sqlite` (in phrases section, after line 334)**

In the SQLite phrases loading loop (where `phrase_entry` is created), after appending to `self._phrase_index` and `self._phrase_surfaces`, add:
```python
# Also index by no-tone key for phrase-span restoration
nt_key = no_tone
self._notone_phrase_index.setdefault(nt_key, []).append(phrase_entry)
```

- [ ] **Populate index in `_load_phrases` (JSON path)**

In `_load_phrases`, after the existing index updates, add:
```python
self._notone_phrase_index.setdefault(no_tone, []).append(phrase_entry)
```

- [ ] **Implement `lookup_phrase_notone`**

```python
def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
    return list(self._notone_phrase_index.get(no_tone_key, []))
```

- [ ] **Run existing tests to verify no regression**

Run: `pytest tests/ -x -q`
Expected: all passing

- [ ] **Commit**

```bash
git add src/vn_corrector/stage2_lexicon/backends/data_store.py
git commit -m "feat: add no-tone phrase index to LexiconDataStore"
```

### Task 1.3: Update FakeLexicon in test_scorer.py

**Files:**
- Modify: `tests/stage5_scorer/test_scorer.py` (FakeLexicon class)

- [ ] **Add `lookup_phrase_notone` to FakeLexicon**

```python
def lookup_phrase_notone(self, no_tone_key: str) -> list[Any]:
    return list(self._PHRASE_NOTONE_MAP.get(no_tone_key, []))
```

Add `_PHRASE_NOTONE_MAP` as a ClassVar:
```python
_PHRASE_NOTONE_MAP: ClassVar[dict[str, list[Any]]] = {}
```

- [ ] **Commit**

```bash
git add tests/stage5_scorer/test_scorer.py
git commit -m "feat: add lookup_phrase_notone to FakeLexicon"
```

---

## Chunk 2: Safety Gate + Lattice Types

### Task 2.1: Safety gate function

**Files:**
- Create: `src/vn_corrector/stage5_scorer/lattice.py` (first part)
- Test: `tests/stage5_scorer/test_lattice.py`

- [ ] **Write failing tests for safety gate**

Create `tests/stage5_scorer/test_lattice.py`:

```python
from vn_corrector.stage5_scorer.lattice import is_safe_phrase_restoration

def test_safe_accentless_to_accented():
    from vn_corrector.common.lexicon import PhraseEntry
    from vn_corrector.common.scoring import Score
    phrase = PhraseEntry(
        entry_id="phrase/test",
        phrase="vậy thì",
        normalized="vay thi",
        no_tone="vay thi",
        n=2,
        score=Score(confidence=0.98),
    )
    assert is_safe_phrase_restoration("vay thi", phrase) is True

def test_unsafe_already_accented():
    from vn_corrector.common.lexicon import PhraseEntry
    from vn_corrector.common.scoring import Score
    phrase = PhraseEntry(
        entry_id="phrase/test",
        phrase="vậy thì",
        normalized="vay thi",
        no_tone="vay thi",
        n=2,
        score=Score(confidence=0.98),
    )
    assert is_safe_phrase_restoration("vậy thì", phrase) is False

def test_unsafe_single_token():
    from vn_corrector.common.lexicon import PhraseEntry
    from vn_corrector.common.scoring import Score
    phrase = PhraseEntry(
        entry_id="phrase/test",
        phrase="một",
        normalized="mot",
        no_tone="mot",
        n=1,
        score=Score(confidence=0.98),
    )
    assert is_safe_phrase_restoration("mot", phrase) is False

def test_unsafe_mismatched_base():
    from vn_corrector.common.lexicon import PhraseEntry
    from vn_corrector.common.scoring import Score
    phrase = PhraseEntry(
        entry_id="phrase/test",
        phrase="vậy thì",
        normalized="vay thi",
        no_tone="vay thi",
        n=2,
        score=Score(confidence=0.98),
    )
    assert is_safe_phrase_restoration("vay khong", phrase) is False

def test_unsafe_foreign_span():
    from vn_corrector.common.lexicon import PhraseEntry
    from vn_corrector.common.scoring import Score
    phrase = PhraseEntry(
        entry_id="phrase/test",
        phrase="iphone",
        normalized="iphone",
        no_tone="iphone",
        n=1,
        score=Score(confidence=0.98),
    )
    assert is_safe_phrase_restoration("iphone", phrase) is False
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/stage5_scorer/test_lattice.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Implement `is_safe_phrase_restoration`**

In `src/vn_corrector/stage5_scorer/lattice.py`:

```python
"""Lattice decoder for phrase-span restoration."""

from __future__ import annotations

from vn_corrector.common.lexicon import PhraseEntry
from vn_corrector.stage1_normalize import strip_accents
from vn_corrector.utils.unicode import contains_vietnamese


def is_safe_phrase_restoration(original_span: str, phrase: PhraseEntry) -> bool:
    """Check if restoring *phrase* from accentless *original_span* is safe.
    
    Returns ``True`` only when all of the following hold:
    1. Stripping accents from both yields the same base form.
    2. The phrase contains Vietnamese accented characters.
    3. The original span is fully accentless (no Vietnamese chars).
    4. The phrase has at least 2 tokens.
    5. Frequency is high enough given the source.
    """
    if strip_accents(phrase.surface).lower() != strip_accents(original_span).lower():
        return False
    if not contains_vietnamese(phrase.surface):
        return False
    if contains_vietnamese(original_span):
        return False
    if phrase.n < 2:
        return False
    freq = phrase.score.confidence
    if freq >= 0.95 and phrase.n >= 3:
        return True
    if freq >= 0.85 and phrase.n >= 2:
        return True
    return False
```

- [ ] **Run tests to verify they pass**

Run: `pytest tests/stage5_scorer/test_lattice.py -v`
Expected: all PASS

- [ ] **Commit**

```bash
git add src/vn_corrector/stage5_scorer/lattice.py tests/stage5_scorer/test_lattice.py
git commit -m "feat: add is_safe_phrase_restoration safety gate"
```

### Task 2.2: LatticeEdge and PhraseSpanEdge types

**Files:**
- Modify: `src/vn_corrector/stage5_scorer/lattice.py`
- Test: `tests/stage5_scorer/test_lattice.py`

- [ ] **Write failing tests for LatticeEdge**

Add to test file:
```python
from vn_corrector.stage5_scorer.lattice import LatticeEdge

def test_lattice_edge_creation():
    edge = LatticeEdge(
        start=0, end=3,
        output_tokens=("vậy", "thì"),
        score=3.5,
        source="phrase_span",
    )
    assert edge.start == 0
    assert edge.end == 3
    assert edge.score == 3.5
    assert edge.source == "phrase_span"
```

- [ ] **Implement LatticeEdge**

Add to `lattice.py`:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class LatticeEdge:
    start: int
    end: int
    output_tokens: tuple[str, ...]
    score: float
    source: str  # "identity", "single_candidate", "phrase_span"
    phrase: PhraseEntry | None = None
```

- [ ] **Run tests**

Run: `pytest tests/stage5_scorer/test_lattice.py -v`
Expected: all PASS

- [ ] **Commit**

```bash
git add src/vn_corrector/stage5_scorer/lattice.py tests/stage5_scorer/test_lattice.py
git commit -m "feat: add LatticeEdge type"
```

---

## Chunk 3: Phrase-Span Proposer

### Task 3.1: PhraseSpanProposer

**Files:**
- Create: `src/vn_corrector/stage4_candidates/phrase_span.py`
- Create: `tests/stage4_candidates/test_phrase_span.py`
- Modify: `src/vn_corrector/stage4_candidates/__init__.py` (export)

- [ ] **Write failing tests for PhraseSpanProposer**

Create `tests/stage4_candidates/test_phrase_span.py`:

```python
from vn_corrector.stage4_candidates.phrase_span import PhraseSpanProposer
from vn_corrector.common.lexicon import LexiconStoreInterface, PhraseEntry, LexiconLookupResult
from vn_corrector.common.scoring import Score
from vn_corrector.common.spans import Token, TextSpan
from vn_corrector.common.enums import TokenType
from typing import ClassVar

class FakePhraseLexicon(LexiconStoreInterface):
    _PHRASES: ClassVar[dict[str, list[PhraseEntry]]] = {
        "vay thi gio phai lam the nao": [
            PhraseEntry(
                entry_id="phrase/test1",
                phrase="vậy thì giờ phải làm thế nào",
                normalized="vay thi gio phai lam the nao",
                no_tone="vay thi gio phai lam the nao",
                n=7, score=Score(confidence=0.99),
            ),
        ],
        "vay thi": [
            PhraseEntry(
                entry_id="phrase/test2",
                phrase="vậy thì",
                normalized="vay thi",
                no_tone="vay thi",
                n=2, score=Score(confidence=0.98),
            ),
        ],
    }
    
    def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
        return list(self._PHRASES.get(no_tone_key, []))
    
    # All other interface methods return empty/defaults

def test_proposer_finds_phrase_span():
    tokens = [
        Token(text="vay", token_type=TokenType.FOREIGN_WORD, span=TextSpan(start=0, end=3)),
        Token(text=" ", token_type=TokenType.SPACE, span=TextSpan(start=3, end=4)),
        Token(text="thi", token_type=TokenType.FOREIGN_WORD, span=TextSpan(start=4, end=7)),
    ]
    proposer = PhraseSpanProposer(lexicon=FakePhraseLexicon())
    edges = proposer.propose(tokens, 0, 3)
    assert len(edges) >= 1
    matching = [e for e in edges if e.output_tokens == ("vậy", "thì")]
    assert len(matching) >= 1
    assert matching[0].start == 0
    assert matching[0].end == 2  # 2 word tokens
```

- [ ] **Run tests to verify they fail**

Run: `pytest tests/stage4_candidates/test_phrase_span.py -v`
Expected: FAIL with ImportError

- [ ] **Implement PhraseSpanProposer**

Create `src/vn_corrector/stage4_candidates/phrase_span.py`:

```python
"""Phrase-span proposer — generates phrase-span edges from token windows."""

from __future__ import annotations

from vn_corrector.common.enums import TokenType
from vn_corrector.common.lexicon import LexiconStoreInterface, PhraseEntry
from vn_corrector.common.spans import Token
from vn_corrector.stage1_normalize import strip_accents
from vn_corrector.stage5_scorer.lattice import LatticeEdge, is_safe_phrase_restoration


class PhraseSpanProposer:
    """Scans token windows and generates safe phrase-span edges."""

    def __init__(self, lexicon: LexiconStoreInterface) -> None:
        self._lexicon = lexicon

    def propose(
        self,
        tokens: list[Token],
        start: int,
        end: int,
    ) -> list[LatticeEdge]:
        """Propose phrase-span edges for token range [start, end)."""
        edges: list[LatticeEdge] = []
        token_slice = tokens[start:end]

        for i in range(len(token_slice)):
            for j in range(i + 2, min(i + 8, len(token_slice)) + 1):
                span_tokens = token_slice[i:j]
                if not all(t.token_type in (TokenType.VI_WORD, TokenType.FOREIGN_WORD, TokenType.UNKNOWN) and t.text.strip() for t in span_tokens):
                    continue
                span_text = " ".join(t.text for t in span_tokens)
                no_tone_key = strip_accents(span_text).lower()
                matches = self._lexicon.lookup_phrase_notone(no_tone_key)
                for phrase in matches:
                    if not is_safe_phrase_restoration(span_text, phrase):
                        continue
                    output_tokens = tuple(phrase.surface.split())
                    score = phrase.score.confidence * (3.5 + min(2.0, 0.25 * phrase.n))
                    edges.append(LatticeEdge(
                        start=start + i,
                        end=start + j,
                        output_tokens=output_tokens,
                        score=score,
                        source="phrase_span",
                        phrase=phrase,
                    ))
        return edges
```

- [ ] **Complete FakePhraseLexicon with all required interface methods**

Add all missing abstract methods returning sensible defaults. Run mypy to verify.

- [ ] **Run tests**

Run: `pytest tests/stage4_candidates/test_phrase_span.py -v`
Expected: PASS

- [ ] **Export from `stage4_candidates/__init__.py`**

Add to `src/vn_corrector/stage4_candidates/__init__.py`:
```python
from vn_corrector.stage4_candidates.phrase_span import PhraseSpanProposer
```

- [ ] **Commit**

```bash
git add src/vn_corrector/stage4_candidates/phrase_span.py tests/stage4_candidates/test_phrase_span.py
git commit -m "feat: add PhraseSpanProposer"
```

---

## Chunk 4: Lattice Decoder

### Task 4.1: Viterbi decoder implementation

**Files:**
- Modify: `src/vn_corrector/stage5_scorer/lattice.py`
- Test: `tests/stage5_scorer/test_lattice.py`

- [ ] **Write failing tests for LatticeDecoder**

```python
from vn_corrector.stage5_scorer.lattice import LatticeEdge, LatticeDecoder

def test_viterbi_single_path():
    edges = [
        LatticeEdge(start=0, end=1, output_tokens=("vay",), score=0.0, source="identity"),
        LatticeEdge(start=1, end=2, output_tokens=("thi",), score=0.0, source="identity"),
        LatticeEdge(start=2, end=3, output_tokens=("gio",), score=0.0, source="identity"),
    ]
    decoder = LatticeDecoder()
    result = decoder.decode(edges, n_tokens=3)
    assert result.best_score is not None
    assert result.tokens == ("vay", "thi", "gio")

def test_viterbi_prefers_phrase_edge():
    edges = [
        LatticeEdge(start=0, end=1, output_tokens=("vay",), score=0.0, source="identity"),
        LatticeEdge(start=1, end=2, output_tokens=("thi",), score=0.0, source="identity"),
        LatticeEdge(start=2, end=3, output_tokens=("gio",), score=0.0, source="identity"),
        LatticeEdge(start=0, end=3, output_tokens=("vậy", "thì", "giờ"), score=4.0, source="phrase_span"),
    ]
    decoder = LatticeDecoder()
    result = decoder.decode(edges, n_tokens=3)
    assert result.tokens == ("vậy", "thì", "giờ")

def test_viterbi_skips_low_score():
    edges = [
        LatticeEdge(start=0, end=1, output_tokens=("vay",), score=0.0, source="identity"),
        LatticeEdge(start=1, end=2, output_tokens=("thi",), score=0.0, source="identity"),
        LatticeEdge(start=0, end=2, output_tokens=("vậy", "thì"), score=0.1, source="phrase_span"),
    ]
    decoder = LatticeDecoder()
    result = decoder.decode(edges, n_tokens=2)
    assert result.tokens == ("vay", "thi")  # identity wins because phrase edge too weak
```

- [ ] **Implement LatticeDecoder**

Add to `lattice.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecodeResult:
    tokens: tuple[str, ...]
    best_score: float
    edges: tuple[LatticeEdge, ...]


class LatticeDecoder:
    """Viterbi-style decoder over token-position lattice edges."""

    def decode(self, edges: list[LatticeEdge], n_tokens: int) -> DecodeResult:
        edges_by_start: dict[int, list[LatticeEdge]] = {}
        for e in edges:
            edges_by_start.setdefault(e.start, []).append(e)

        best_score = [float("-inf")] * (n_tokens + 1)
        best_edge: list[LatticeEdge | None] = [None] * (n_tokens + 1)
        best_score[0] = 0.0

        for i in range(n_tokens):
            if best_score[i] == float("-inf"):
                continue
            for edge in edges_by_start.get(i, []):
                j = edge.end
                new_score = best_score[i] + edge.score
                if new_score > best_score[j]:
                    best_score[j] = new_score
                    best_edge[j] = edge

        # Backtrace
        result_edges: list[LatticeEdge] = []
        pos = n_tokens
        while pos > 0 and best_edge[pos] is not None:
            edge = best_edge[pos]
            if edge is None:
                break
            result_edges.append(edge)
            pos = edge.start
        result_edges.reverse()

        # Build output tokens
        tokens: list[str] = []
        for edge in result_edges:
            tokens.extend(edge.output_tokens)

        return DecodeResult(
            tokens=tuple(tokens),
            best_score=best_score[n_tokens] if best_score[n_tokens] != float("-inf") else 0.0,
            edges=tuple(result_edges),
        )
```

- [ ] **Run tests**

Run: `pytest tests/stage5_scorer/test_lattice.py -v`
Expected: all PASS

- [ ] **Commit**

```bash
git add src/vn_corrector/stage5_scorer/lattice.py tests/stage5_scorer/test_lattice.py
git commit -m "feat: add Viterbi LatticeDecoder"
```

---

## Chunk 5: Pipeline Integration

### Task 5.1: Wire phrase-span into correction pipeline

**Files:**
- Modify: `src/vn_corrector/pipeline/corrector.py`

- [ ] **Add phrase-span step in `_run_pipeline`**

After candidate generation (line ~221, after `cand_doc = ...`), add:

```python
# --- Step 5b: Phrase-span restoration ---
phrase_edges: list[LatticeEdge] = []
if ctx.config.enable_phrase_span_restoration:
    from vn_corrector.stage4_candidates.phrase_span import PhraseSpanProposer
    proposer = PhraseSpanProposer(lexicon=ctx.lexicon)
    phrase_edges = proposer.propose(tokens, 0, len(tokens))
```

Then after windows scoring + decision (after line ~260), add phrase-span edge merging:

```python
# --- Step 8b: Merge phrase-span corrections ---
if phrase_edges:
    from vn_corrector.stage5_scorer.lattice import LatticeDecoder
    all_edges: list[LatticeEdge] = list(phrase_edges)
    # Add identity edges for all tokens
    for i, t in enumerate(tokens):
        all_edges.append(LatticeEdge(
            start=i, end=i+1,
            output_tokens=(t.text,),
            score=0.0,
            source="identity",
        ))
    decoder = LatticeDecoder()
    decode_result = decoder.decode(all_edges, len(tokens))
    
    if decode_result.best_score > 0:
        phrase_changes: list[CorrectionChange] = []
        for edge in decode_result.edges:
            if edge.source == "phrase_span":
                span_tokens = tokens[edge.start:edge.end]
                orig_text = "".join(t.text for t in span_tokens)
                replacement_text = "".join(
                    edge.output_tokens[i] if i < len(edge.output_tokens) and
                    not t.text.strip() else t.text
                    for i, t in enumerate(span_tokens)
                )
                # Find char offsets
                char_start = span_tokens[0].span.start
                char_end = span_tokens[-1].span.end
                # Create change but prefer higher-score over existing non-phrase changes
                phrase_changes.append(CorrectionChange(
                    original=orig_text,
                    replacement=replacement_text,
                    span=TextSpan(start=char_start, end=char_end),
                    confidence=min(1.0, edge.score / 5.0),
                    reason=f"phrase_span_restoration: {orig_text} -> {replacement_text}",
                    decision="replace",
                    candidate_sources=["phrase_span"],
                ))
        for pc in phrase_changes:
            if not any(
                c.span.start == pc.span.start and c.span.end == pc.span.end
                for c in accepted
            ):
                accepted.append(pc)
```

- [ ] **Add config flag for phrase-span restoration**

In `src/vn_corrector/pipeline/config.py`, add:
```python
enable_phrase_span_restoration: bool = True
```

- [ ] **Commit**

```bash
git add src/vn_corrector/pipeline/corrector.py src/vn_corrector/pipeline/config.py
git commit -m "feat: wire phrase-span restoration into correction pipeline"
```

---

## Chunk 6: Acceptance Tests

### Task 6.1: Add positive and negative acceptance tests

**Files:**
- Modify: `tests/stage5_scorer/test_acceptance.py`

- [ ] **Write failing acceptance tests**

```python
def test_accentless_phrase_restoration_vay_thi_gio():
    """Long accentless phrase should be fully restored via phrase-span."""
    from vn_corrector.pipeline import correct_text
    result = correct_text("vay thi gio phai lam the nao ???")
    assert "vậy" in result.corrected_text
    assert "thì" in result.corrected_text
    assert "giờ" in result.corrected_text
    assert "phải" in result.corrected_text
    assert "làm" in result.corrected_text
    assert "thế" in result.corrected_text
    assert "nào" in result.corrected_text

def test_accentless_phrase_restoration_moi_quan_he():
    result = correct_text("moi quan he")
    assert "mối" in result.corrected_text or "mọi" in result.corrected_text
    assert "hệ" in result.corrected_text

def test_foreign_word_protected_in_phrase_restoration():
    """Protected words like iphone must not be force-accented."""
    result = correct_text("iphone moi ra")
    assert "iphone" in result.corrected_text.lower()

def test_ambiguous_short_no_tone_not_overcorrected():
    """'ma' alone must remain unchanged (too ambiguous)."""
    result = correct_text("ma")
    assert result.corrected_text == "ma"

def test_ma_tuy_corrected_with_phrase_evidence():
    """'ma tuy' has phrase evidence 'ma túy'."""
    result = correct_text("ma tuy")
    assert "túy" in result.corrected_text
```

- [ ] **Run acceptance tests**

Run: `pytest tests/stage5_scorer/test_acceptance.py -v -k "phrase_restoration or foreign or ambiguous or ma_tuy"`
Expected: pass (or some fail due to missing phrase data — fix data if needed)

- [ ] **Commit**

```bash
git add tests/stage5_scorer/test_acceptance.py
git commit -m "test: add acceptance tests for M6.1 phrase-span restoration"
```

---

## Chunk 7: Final Verification

- [ ] **Run full CI suite**

```bash
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```

Fix any issues.

- [ ] **Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: address review feedback"
```
