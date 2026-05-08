# M6.1: Production Phrase-Span Lattice Decoder for Reliable No-Tone Vietnamese Restoration

> **For agentic workers:** REQUIRED: Use `superpowers:subagent-driven-development` if subagents are available, otherwise use `superpowers:executing-plans`. Track progress using checkbox (`- [ ]`) syntax.

## Goal

Add a production-grade phrase-span lattice decoder that reliably restores multiple adjacent accentless Vietnamese tokens using:

1. A safe no-tone phrase index
2. Word-island phrase-span proposal
3. Weighted lattice edges
4. Viterbi decoding
5. Evidence/risk decision gate
6. Conflict-safe pipeline integration

This should fix cases where correct output requires multiple adjacent tokens to change together before phrase/ngram evidence becomes visible.

Example:

```text
vay thi gio phai lam the nao ???
````

Expected:

```text
vậy thì giờ phải làm thế nào ???
```

Current failure mode:

```text
vay thi gio phai lam the nao ???
```

Root cause:

* Single-token changes do not receive phrase/ngram evidence.
* Example: `vay -> vậy` produces `vậy thi`, which does not match `vậy thì`.
* The fully corrected path would score well, but it is buried by combinatorial explosion.
* Therefore, the correction must be represented as a phrase-span edge, not seven independent token edits.

---

# Architecture

## New components

```text
1. No-tone phrase index in LexiconDataStore
2. WordIslandExtractor
3. PhraseSpanProposer
4. LatticeEdge + LatticeDecoder
5. Phrase-span decision/conflict gate
6. Pipeline integration after candidate generation
```

## Important production rule

The lattice must decode over **word-island positions**, not raw tokenizer indexes.

Raw tokenizer output may look like:

```text
[vay][ ][thi][ ][gio][ ][phai][ ][lam][ ][the][ ][nao][ ][???]
```

But the lattice should operate over:

```text
word_index 0 -> raw token index 0 -> vay
word_index 1 -> raw token index 2 -> thi
word_index 2 -> raw token index 4 -> gio
...
```

This prevents spaces and punctuation from breaking phrase matching.

Each lattice edge should carry both:

```text
word span: used by decoder
raw token / char span: used for replacement reconstruction
```

---

# Files

| File                                                     | Action | Responsibility                                                                            |
| -------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------- |
| `src/vn_corrector/common/lexicon.py`                     | Modify | Add `lookup_phrase_notone()` to `LexiconStoreInterface`                                   |
| `src/vn_corrector/stage2_lexicon/backends/data_store.py` | Modify | Add `_notone_phrase_index`, populate from SQLite/JSON, implement `lookup_phrase_notone()` |
| `src/vn_corrector/stage4_candidates/word_island.py`      | Create | Extract word-like correction islands from raw tokens                                      |
| `src/vn_corrector/stage4_candidates/phrase_span.py`      | Create | Generate safe phrase-span lattice edges over word islands                                 |
| `src/vn_corrector/stage5_scorer/lattice.py`              | Create | `LatticeEdge`, `DecodeResult`, `LatticeDecoder`, safety gate                              |
| `src/vn_corrector/pipeline/config.py`                    | Modify | Add phrase-span config flags                                                              |
| `src/vn_corrector/pipeline/corrector.py`                 | Modify | Wire phrase-span restoration into pipeline                                                |
| `tests/stage4_candidates/test_word_island.py`            | Create | Tests for word-island extraction                                                          |
| `tests/stage4_candidates/test_phrase_span.py`            | Create | Tests for phrase-span proposal                                                            |
| `tests/stage5_scorer/test_lattice.py`                    | Create | Tests for safety gate + Viterbi decoder                                                   |
| `tests/stage5_scorer/test_acceptance.py`                 | Modify | Add M6.1 acceptance tests                                                                 |

---

# Chunk 1: No-Tone Phrase Index

## Task 1.1: Add `lookup_phrase_notone()` to `LexiconStoreInterface`

**Files:**

* Modify: `src/vn_corrector/common/lexicon.py`

* [ ] Add method to `LexiconStoreInterface`, near existing phrase lookup methods:

```python
@abstractmethod
def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
    """Return phrase entries matching an accent-stripped phrase key."""
    ...
```

* [ ] Run type checks for interface consumers:

```bash
mypy src tests
```

* [ ] Commit:

```bash
git add src/vn_corrector/common/lexicon.py
git commit -m "feat: add lookup_phrase_notone to lexicon interface"
```

---

## Task 1.2: Add no-tone phrase index to `LexiconDataStore`

**Files:**

* Modify: `src/vn_corrector/stage2_lexicon/backends/data_store.py`

* [ ] Add index in `LexiconDataStore.__init__`:

```python
self._notone_phrase_index: dict[str, list[PhraseEntry]] = {}
```

* [ ] Populate index when loading phrases from SQLite.

Wherever a `PhraseEntry` is created and added to the existing phrase indexes, also add:

```python
nt_key = phrase_entry.no_tone
self._notone_phrase_index.setdefault(nt_key, []).append(phrase_entry)
```

If the real field is not `no_tone`, use the existing normalized/accent-stripped field. Do not recompute differently from the rest of the lexicon pipeline.

* [ ] Populate index when loading phrases from JSON/resources:

```python
self._notone_phrase_index.setdefault(phrase_entry.no_tone, []).append(phrase_entry)
```

* [ ] Implement:

```python
def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
    key = no_tone_key.strip().lower()
    return list(self._notone_phrase_index.get(key, []))
```

* [ ] Verify the index can return multiple entries for the same no-tone key.

No-tone keys are ambiguous in Vietnamese, so this must return `list[PhraseEntry]`, not a single phrase.

* [ ] Run:

```bash
pytest tests/ -x -q
mypy src tests
```

* [ ] Commit:

```bash
git add src/vn_corrector/stage2_lexicon/backends/data_store.py
git commit -m "feat: add no-tone phrase index to data store"
```

---

## Task 1.3: Update fake lexicons in tests

**Files:**

* Modify fake lexicons in existing tests, especially `tests/stage5_scorer/test_scorer.py`

* [ ] Add:

```python
_PHRASE_NOTONE_MAP: ClassVar[dict[str, list[PhraseEntry]]] = {}

def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]:
    return list(self._PHRASE_NOTONE_MAP.get(no_tone_key.strip().lower(), []))
```

* [ ] Ensure all abstract interface methods are implemented by fake lexicons.

* [ ] Run:

```bash
pytest tests/stage5_scorer/test_scorer.py -q
mypy tests/stage5_scorer/test_scorer.py
```

* [ ] Commit:

```bash
git add tests/stage5_scorer/test_scorer.py
git commit -m "test: add lookup_phrase_notone to fake lexicons"
```

---

# Chunk 2: Word-Island Extraction

## Purpose

Phrase-span restoration should run over word-like islands only.

Example raw tokens:

```text
[vay][ ][thi][ ][gio][ ][???][ ][iphone][ ][15]
```

Correction islands:

```text
Island 1: vay thi gio
Island 2: iphone
```

But phrase restoration should reject protected/foreign/product-heavy islands unless safe phrase evidence exists.

---

## Task 2.1: Create word island types

**Files:**

* Create: `src/vn_corrector/stage4_candidates/word_island.py`

* Create: `tests/stage4_candidates/test_word_island.py`

* [ ] Add type:

```python
from dataclasses import dataclass
from vn_corrector.common.spans import Token, TextSpan


@dataclass(frozen=True)
class WordIsland:
    """A contiguous correction island over word-like tokens.

    word_tokens are the word-like tokens only.
    raw_start/raw_end are raw token indexes in the original token list.
    char_span is the full character span from the first to last word token.
    """

    word_tokens: tuple[Token, ...]
    raw_token_indexes: tuple[int, ...]
    raw_start: int
    raw_end: int
    char_span: TextSpan
```

* [ ] Define word-like token types.

Use the actual enum names in the project. Conceptually:

```python
WORD_LIKE_TOKEN_TYPES = {
    TokenType.VI_WORD,
    TokenType.FOREIGN_WORD,
    TokenType.UNKNOWN,
}
```

Do not include:

```text
SPACE
PUNCT
NUMBER
URL
EMAIL
PROTECTED
```

unless the existing project uses different names.

---

## Task 2.2: Implement `extract_word_islands()`

* [ ] Implement:

```python
def extract_word_islands(tokens: list[Token]) -> list[WordIsland]:
    """Extract contiguous word-like correction islands.

    Spaces may exist between word tokens and should not break the island.
    Punctuation/protected/non-word tokens should break the island.
    """
```

Important behavior:

```text
[vay][ ][thi][ ][gio] -> one island with 3 word tokens
[vay][ ][thi][???] -> one island for vay thi, punctuation breaks after
[iphone][ ][15][ ][pro] -> do not include number if NUMBER is not word-like
```

Implementation idea:

```python
def extract_word_islands(tokens: list[Token]) -> list[WordIsland]:
    islands: list[WordIsland] = []
    current_word_tokens: list[Token] = []
    current_raw_indexes: list[int] = []

    for raw_idx, token in enumerate(tokens):
        if is_word_like_token(token):
            current_word_tokens.append(token)
            current_raw_indexes.append(raw_idx)
            continue

        if token.token_type == TokenType.SPACE:
            # Spaces do not break an active word island.
            continue

        # Punctuation/protected/non-word breaks island.
        flush_current()

    flush_current()
    return islands
```

* [ ] `raw_start` should be first raw token index of the island.
* [ ] `raw_end` should be last raw token index + 1.
* [ ] `char_span.start` should be first word token start.
* [ ] `char_span.end` should be last word token end.

---

## Task 2.3: Tests for word islands

**Files:**

* Create: `tests/stage4_candidates/test_word_island.py`

* [ ] Add tests:

```python
def test_extracts_words_across_spaces():
    # [vay][ ][thi][ ][gio] -> one island of 3 word tokens
```

```python
def test_punctuation_breaks_island():
    # [vay][ ][thi][???][gio] -> two islands
```

```python
def test_preserves_raw_token_indexes():
    # word positions should map back to raw token indexes
```

```python
def test_empty_when_no_word_tokens():
    # punctuation/spaces only -> []
```

* [ ] Run:

```bash
pytest tests/stage4_candidates/test_word_island.py -v
```

* [ ] Commit:

```bash
git add src/vn_corrector/stage4_candidates/word_island.py tests/stage4_candidates/test_word_island.py
git commit -m "feat: add word-island extraction for phrase restoration"
```

---

# Chunk 3: Lattice Types + Safety Gates

## Task 3.1: Create `lattice.py`

**Files:**

* Create: `src/vn_corrector/stage5_scorer/lattice.py`
* Create: `tests/stage5_scorer/test_lattice.py`

---

## Task 3.2: Implement safe phrase restoration gate

* [ ] Implement helper to get phrase text.

Use the real `PhraseEntry` field names. If uncertain, add a small helper:

```python
def get_phrase_surface(phrase: PhraseEntry) -> str:
    """Return canonical phrase surface text."""
    return getattr(phrase, "surface", None) or getattr(phrase, "phrase")
```

Prefer standardizing on the real model field if possible.

* [ ] Implement:

```python
def is_safe_phrase_restoration(original_span: str, phrase: PhraseEntry) -> bool:
    """Return True if phrase can safely restore an accentless original span."""
```

Rules:

```text
1. strip_accents(phrase_surface).lower() == strip_accents(original_span).lower()
2. phrase_surface contains Vietnamese accented characters
3. original_span contains no Vietnamese accented characters
4. phrase has at least 2 tokens
5. phrase confidence/frequency passes threshold
```

Pseudo:

```python
def is_safe_phrase_restoration(original_span: str, phrase: PhraseEntry) -> bool:
    surface = get_phrase_surface(phrase)
    original_key = strip_accents(original_span).lower().strip()
    phrase_key = strip_accents(surface).lower().strip()

    if phrase_key != original_key:
        return False

    if not contains_vietnamese(surface):
        return False

    if contains_vietnamese(original_span):
        return False

    n = getattr(phrase, "n", len(surface.split()))
    if n < 2:
        return False

    confidence = phrase.score.confidence

    # Trusted/curated metadata can be added later. For MVP use freq/length.
    if confidence >= 0.95 and n >= 3:
        return True

    if confidence >= 0.85 and n >= 2:
        return True

    return False
```

* [ ] Add tests:

```python
def test_safe_accentless_to_accented_phrase():
    # "vay thi" -> "vậy thì" safe
```

```python
def test_unsafe_already_accented_original():
    # "vậy thi" should not be phrase-restored by this layer
```

```python
def test_unsafe_single_token():
    # "ma" -> "mà" rejected
```

```python
def test_unsafe_mismatched_base():
    # "vay khong" does not match "vậy thì"
```

```python
def test_unsafe_candidate_without_vietnamese_accents():
    # "iphone" rejected
```

* [ ] Run:

```bash
pytest tests/stage5_scorer/test_lattice.py -v
```

---

## Task 3.3: Add `LatticeEdge`

* [ ] Implement:

```python
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LatticeEdge:
    """A weighted edge in the phrase restoration lattice.

    start/end are word-island positions, not raw token positions.
    raw_start/raw_end are raw token positions for reconstruction.
    char_start/char_end are source character offsets.
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
```

* [ ] Tests:

```python
def test_lattice_edge_creation():
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
        explanation="trusted phrase"
    )
    assert edge.start == 0
    assert edge.end == 2
    assert edge.raw_start == 0
    assert edge.raw_end == 3
```

* [ ] Commit:

```bash
git add src/vn_corrector/stage5_scorer/lattice.py tests/stage5_scorer/test_lattice.py
git commit -m "feat: add lattice edge and phrase safety gate"
```

---

# Chunk 4: PhraseSpanProposer

## Task 4.1: Implement proposer over word islands

**Files:**

* Create: `src/vn_corrector/stage4_candidates/phrase_span.py`
* Create: `tests/stage4_candidates/test_phrase_span.py`
* Modify: `src/vn_corrector/stage4_candidates/__init__.py`

---

## Task 4.2: Implement `PhraseSpanProposer`

* [ ] Create:

```python
class PhraseSpanProposer:
    """Generate safe phrase-span lattice edges over a WordIsland."""

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
```

* [ ] Implement:

```python
def propose_for_island(self, island: WordIsland) -> list[LatticeEdge]:
    """Generate phrase-span edges for one word island."""
```

Algorithm:

```python
word_tokens = island.word_tokens

for i in range(len(word_tokens)):
    max_j = min(len(word_tokens), i + self._max_len)
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
                # Reject phrase/tokenization mismatch for MVP.
                continue

            score = compute_phrase_span_score(phrase)
            risk = compute_phrase_span_risk(phrase, original_span)

            raw_start = island.raw_token_indexes[i]
            raw_end = island.raw_token_indexes[j - 1] + 1
            char_start = span_tokens[0].span.start
            char_end = span_tokens[-1].span.end

            yield LatticeEdge(...)
```

* [ ] Implement score helper:

```python
def compute_phrase_span_score(phrase: PhraseEntry) -> float:
    n = getattr(phrase, "n", len(get_phrase_surface(phrase).split()))
    confidence = phrase.score.confidence
    base = 3.5
    length_bonus = min(2.0, 0.25 * n)
    return confidence * (base + length_bonus)
```

* [ ] Implement risk helper:

```python
def compute_phrase_span_risk(phrase: PhraseEntry, original_span: str) -> float:
    n = getattr(phrase, "n", len(get_phrase_surface(phrase).split()))
    confidence = phrase.score.confidence

    # Long high-confidence phrase is low risk.
    risk = max(0.0, 1.0 - confidence)

    # Short phrases are more ambiguous.
    if n == 2:
        risk += 0.15

    return min(1.0, risk)
```

* [ ] Implement:

```python
def propose(self, islands: list[WordIsland]) -> list[LatticeEdge]:
    edges = []
    for island in islands:
        edges.extend(self.propose_for_island(island))
    return edges
```

---

## Task 4.3: Tests for `PhraseSpanProposer`

* [ ] Fake lexicon should include:

```text
vay thi -> vậy thì
vay thi gio phai lam the nao -> vậy thì giờ phải làm thế nào
moi quan he -> mối quan hệ
ma -> mà
iphone -> iphone
```

* [ ] Tests:

```python
def test_proposer_finds_phrase_across_spaces():
    # raw tokens [vay][ ][thi]
    # word island has 2 word tokens
    # proposer emits edge output ("vậy", "thì")
```

```python
def test_proposer_uses_word_indexes_not_raw_indexes():
    # edge.start == 0, edge.end == 2
    # edge.raw_start points to raw token index of "vay"
    # edge.raw_end points after raw token index of "thi"
```

```python
def test_proposer_rejects_single_token_phrase():
    # "ma" -> "mà" rejected
```

```python
def test_proposer_rejects_mismatched_phrase():
    # no edge when stripped forms do not match
```

```python
def test_proposer_scores_long_phrase_above_short_phrase():
    # long phrase has higher score due to length bonus
```

* [ ] Export:

```python
from vn_corrector.stage4_candidates.phrase_span import PhraseSpanProposer
```

* [ ] Run:

```bash
pytest tests/stage4_candidates/test_word_island.py tests/stage4_candidates/test_phrase_span.py -v
mypy src tests
```

* [ ] Commit:

```bash
git add src/vn_corrector/stage4_candidates/phrase_span.py src/vn_corrector/stage4_candidates/__init__.py tests/stage4_candidates/test_phrase_span.py
git commit -m "feat: add phrase-span proposer over word islands"
```

---

# Chunk 5: Viterbi Lattice Decoder

## Task 5.1: Add decode result

**Files:**

* Modify: `src/vn_corrector/stage5_scorer/lattice.py`

* Modify: `tests/stage5_scorer/test_lattice.py`

* [ ] Implement:

```python
@dataclass(frozen=True)
class DecodeResult:
    tokens: tuple[str, ...]
    best_score: float
    original_score: float
    score_margin: float
    total_risk: float
    edges: tuple[LatticeEdge, ...]

    @property
    def changed(self) -> bool:
        return any(edge.source != "identity" for edge in self.edges)
```

---

## Task 5.2: Implement `LatticeDecoder`

* [ ] Implement:

```python
class LatticeDecoder:
    """Viterbi-style decoder over word-position lattice edges."""

    def decode(self, edges: list[LatticeEdge], n_words: int) -> DecodeResult:
        ...
```

Algorithm:

```python
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

        # Prefer higher score, then lower risk.
        if (
            new_score > best_score[j]
            or (new_score == best_score[j] and new_risk < best_risk[j])
        ):
            best_score[j] = new_score
            best_risk[j] = new_risk
            best_edge[j] = edge
```

Backtrace:

```python
result_edges = []
pos = n_words

while pos > 0:
    edge = best_edge[pos]
    if edge is None:
        # No complete path. Return empty/fallback result.
        ...
    result_edges.append(edge)
    pos = edge.start

result_edges.reverse()
```

Output:

```python
tokens = []
for edge in result_edges:
    tokens.extend(edge.output_tokens)
```

Compute original score:

```python
original_score = sum(
    edge.score
    for edge in result_edges
    if edge.source == "identity"
)
```

Better: identity path baseline should be calculated from identity edges directly. For MVP, identity edge score can be `0.0`, so:

```python
original_score = 0.0
score_margin = best_score[n_words] - original_score
```

Return:

```python
DecodeResult(
    tokens=tuple(tokens),
    best_score=best_score[n_words],
    original_score=original_score,
    score_margin=score_margin,
    total_risk=best_risk[n_words],
    edges=tuple(result_edges),
)
```

---

## Task 5.3: Tests for decoder

* [ ] Add tests:

```python
def test_viterbi_identity_path():
    # identity edges produce original tokens
```

```python
def test_viterbi_prefers_phrase_edge():
    # phrase edge 0 -> 3 beats identity edges
```

```python
def test_viterbi_prefers_lower_risk_on_equal_score():
    # equal scores, lower risk wins
```

```python
def test_viterbi_combines_non_overlapping_phrase_edges():
    # 0 -> 2 phrase + 2 -> 5 phrase
```

```python
def test_viterbi_rejects_invalid_edge_bounds():
    # edge end > n_words ignored
```

* [ ] Run:

```bash
pytest tests/stage5_scorer/test_lattice.py -v
```

* [ ] Commit:

```bash
git add src/vn_corrector/stage5_scorer/lattice.py tests/stage5_scorer/test_lattice.py
git commit -m "feat: add Viterbi lattice decoder"
```

---

# Chunk 6: Phrase-Span Decision Gate

## Purpose

Do not blindly accept the highest scoring lattice path.

Accept only if:

```text
score_margin >= phrase_span_accept_margin
and total_risk <= phrase_span_risk_threshold
```

This protects against ambiguous no-tone corrections.

---

## Task 6.1: Add config flags

**Files:**

* Modify: `src/vn_corrector/pipeline/config.py`

* [ ] Add:

```python
enable_phrase_span_restoration: bool = True
phrase_span_min_len: int = 2
phrase_span_max_len: int = 8
phrase_span_accept_margin: float = 2.0
phrase_span_risk_threshold: float = 0.5
phrase_span_preserve_spacing: bool = True
```

Tune later after acceptance tests.

* [ ] Commit:

```bash
git add src/vn_corrector/pipeline/config.py
git commit -m "feat: add phrase-span restoration config"
```

---

## Task 6.2: Add helper to convert decoded phrase edges to changes

**Files:**

* Modify or create helper in `src/vn_corrector/stage5_scorer/lattice.py`

* [ ] Implement replacement reconstruction.

MVP simple reconstruction:

```python
replacement_text = " ".join(edge.output_tokens)
```

Better production reconstruction preserving original separators:

```python
def reconstruct_phrase_replacement(
    raw_tokens: list[Token],
    edge: LatticeEdge,
) -> str:
    """Replace word tokens in edge span while preserving separators."""
```

Algorithm:

```text
For raw tokens from edge.raw_start to edge.raw_end:
- If token is a word token participating in the edge, replace with next output token.
- If token is space/punctuation inside the raw span, preserve as-is.
```

Pseudo:

```python
def reconstruct_phrase_replacement(raw_tokens: list[Token], edge: LatticeEdge) -> str:
    assert edge.raw_start is not None
    assert edge.raw_end is not None

    output_iter = iter(edge.output_tokens)
    pieces = []

    for token in raw_tokens[edge.raw_start:edge.raw_end]:
        if is_word_like_token(token):
            pieces.append(next(output_iter))
        else:
            pieces.append(token.text)

    return "".join(pieces)
```

This preserves:

```text
vay   thi -> vậy   thì
```

* [ ] Add tests:

```python
def test_reconstruct_preserves_spaces():
    # "vay   thi" -> "vậy   thì"
```

```python
def test_reconstruct_simple_space():
    # "vay thi" -> "vậy thì"
```

---

# Chunk 7: Pipeline Integration

## Task 7.1: Integrate phrase-span restoration

**Files:**

* Modify: `src/vn_corrector/pipeline/corrector.py`

## Recommended integration shape

Current pipeline roughly:

```text
normalize
-> tokenize
-> protect
-> candidate generation
-> scoring
-> decision
```

M6.1 phrase restoration should run after tokenization/protection/candidate generation, but before final result assembly.

For MVP, phrase-span changes can be merged after existing accepted changes **only with conflict resolution**.

---

## Task 7.2: Generate phrase-span edges

* [ ] After tokenization and candidate generation:

```python
phrase_changes: list[CorrectionChange] = []

if ctx.config.enable_phrase_span_restoration:
    islands = extract_word_islands(tokens)

    proposer = PhraseSpanProposer(
        lexicon=ctx.lexicon,
        min_len=ctx.config.phrase_span_min_len,
        max_len=ctx.config.phrase_span_max_len,
    )

    for island in islands:
        phrase_edges = proposer.propose_for_island(island)

        if not phrase_edges:
            continue

        all_edges = build_identity_edges_for_island(island)
        all_edges.extend(phrase_edges)

        decode_result = LatticeDecoder().decode(
            all_edges,
            n_words=len(island.word_tokens),
        )

        if not should_accept_phrase_decode(decode_result, ctx.config):
            continue

        phrase_changes.extend(
            decode_result_to_changes(
                decode_result=decode_result,
                raw_tokens=tokens,
            )
        )
```

---

## Task 7.3: Identity edges

* [ ] Add helper:

```python
def build_identity_edges_for_island(island: WordIsland) -> list[LatticeEdge]:
    edges = []

    for word_idx, token in enumerate(island.word_tokens):
        raw_idx = island.raw_token_indexes[word_idx]
        edges.append(
            LatticeEdge(
                start=word_idx,
                end=word_idx + 1,
                output_tokens=(token.text,),
                score=0.0,
                risk=0.0,
                source="identity",
                raw_start=raw_idx,
                raw_end=raw_idx + 1,
                char_start=token.span.start,
                char_end=token.span.end,
                explanation="identity",
            )
        )

    return edges
```

---

## Task 7.4: Decision gate

* [ ] Add:

```python
def should_accept_phrase_decode(
    result: DecodeResult,
    config: CorrectorConfig,
) -> bool:
    if not result.changed:
        return False

    if result.score_margin < config.phrase_span_accept_margin:
        return False

    if result.total_risk > config.phrase_span_risk_threshold:
        return False

    return True
```

---

## Task 7.5: Convert decoded edges to `CorrectionChange`

* [ ] For every edge where `edge.source == "phrase_span"`:

```python
original_text = source_text[edge.char_start:edge.char_end]
replacement_text = reconstruct_phrase_replacement(tokens, edge)
```

Create a `CorrectionChange` using the project’s actual field names.

Conceptual fields:

```python
CorrectionChange(
    original=original_text,
    replacement=replacement_text,
    span=TextSpan(start=edge.char_start, end=edge.char_end),
    confidence=min(1.0, edge.score / 5.5),
    reason=ChangeReason.PHRASE_SPAN_RESTORATION,
    candidate_sources=["phrase_span"],
)
```

Use the real enum/type names in the project.

---

## Task 7.6: Conflict resolution with existing accepted changes

Phrase-span changes should win over smaller overlapping token changes when:

```text
1. phrase change has high score
2. phrase change fully covers smaller token-level changes
3. phrase span contains no protected tokens
4. phrase change passed risk gate
```

* [ ] Implement helper:

```python
def merge_phrase_changes(
    accepted: list[CorrectionChange],
    phrase_changes: list[CorrectionChange],
) -> list[CorrectionChange]:
    ...
```

Rules:

```text
- If no overlap, keep both.
- If phrase change overlaps existing smaller changes, remove covered smaller changes and keep phrase.
- If existing change partially overlaps phrase without full coverage, keep existing and reject phrase.
- Sort final changes by span.start.
```

Pseudo:

```python
def spans_overlap(a: TextSpan, b: TextSpan) -> bool:
    return a.start < b.end and b.start < a.end

def span_covers(a: TextSpan, b: TextSpan) -> bool:
    return a.start <= b.start and a.end >= b.end
```

Merge logic:

```python
merged = list(accepted)

for phrase_change in phrase_changes:
    overlaps = [c for c in merged if spans_overlap(c.span, phrase_change.span)]

    if not overlaps:
        merged.append(phrase_change)
        continue

    if all(span_covers(phrase_change.span, c.span) for c in overlaps):
        merged = [c for c in merged if c not in overlaps]
        merged.append(phrase_change)
        continue

    # Partial overlap is unsafe. Reject phrase change.
    continue

return sorted(merged, key=lambda c: c.span.start)
```

---

## Task 7.7: Run integration tests

* [ ] Run targeted tests:

```bash
pytest tests/stage4_candidates/test_word_island.py -v
pytest tests/stage4_candidates/test_phrase_span.py -v
pytest tests/stage5_scorer/test_lattice.py -v
```

* [ ] Commit:

```bash
git add src/vn_corrector/pipeline/corrector.py src/vn_corrector/pipeline/config.py src/vn_corrector/stage5_scorer/lattice.py
git commit -m "feat: integrate phrase-span lattice restoration"
```

---

# Chunk 8: Phrase Data

## Task 8.1: Add required phrase entries

Phrase-span restoration only works if trusted phrase data exists.

Add or verify these entries in the existing phrase resource / trusted SQLite source:

```json
[
  {
    "surface": "vậy thì",
    "normalized": "vay thi",
    "no_tone": "vay thi",
    "domain": "general",
    "freq": 0.98,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "thì giờ",
    "normalized": "thi gio",
    "no_tone": "thi gio",
    "domain": "general",
    "freq": 0.95,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "làm thế nào",
    "normalized": "lam the nao",
    "no_tone": "lam the nao",
    "domain": "general",
    "freq": 0.98,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "vậy thì giờ phải làm thế nào",
    "normalized": "vay thi gio phai lam the nao",
    "no_tone": "vay thi gio phai lam the nao",
    "domain": "general",
    "freq": 0.99,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "mối quan hệ",
    "normalized": "moi quan he",
    "no_tone": "moi quan he",
    "domain": "general",
    "freq": 0.99,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "quan hệ",
    "normalized": "quan he",
    "no_tone": "quan he",
    "domain": "general",
    "freq": 0.98,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "không biết làm sao",
    "normalized": "khong biet lam sao",
    "no_tone": "khong biet lam sao",
    "domain": "general",
    "freq": 0.98,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "có gì đâu",
    "normalized": "co gi dau",
    "no_tone": "co gi dau",
    "domain": "general",
    "freq": 0.98,
    "source": "curated",
    "trust": "high"
  },
  {
    "surface": "ma túy",
    "normalized": "ma tuy",
    "no_tone": "ma tuy",
    "domain": "general",
    "freq": 0.97,
    "source": "curated",
    "trust": "high"
  }
]
```

Use the project’s actual phrase schema. Do not add duplicate/conflicting field names if the schema already uses `phrase` instead of `surface`.

* [ ] Rebuild trusted lexicon/resources if required.

* [ ] Commit:

```bash
git add resources/ src/ tests/
git commit -m "data: add curated phrases for phrase-span restoration"
```

---

# Chunk 9: Acceptance Tests

## Task 9.1: Add positive tests

**Files:**

* Modify: `tests/stage5_scorer/test_acceptance.py`

* [ ] Add exact positive tests:

```python
def test_phrase_span_restores_vay_thi_gio_phai_lam_the_nao():
    result = correct_text("vay thi gio phai lam the nao ???")
    assert result.corrected_text == "vậy thì giờ phải làm thế nào ???"
```

```python
def test_phrase_span_restores_moi_quan_he():
    result = correct_text("moi quan he")
    assert result.corrected_text == "mối quan hệ"
```

```python
def test_phrase_span_restores_quan_he():
    result = correct_text("quan he")
    assert result.corrected_text == "quan hệ"
```

```python
def test_phrase_span_restores_lam_the_nao():
    result = correct_text("lam the nao")
    assert result.corrected_text == "làm thế nào"
```

```python
def test_phrase_span_restores_khong_biet_lam_sao():
    result = correct_text("khong biet lam sao")
    assert result.corrected_text == "không biết làm sao"
```

```python
def test_phrase_span_restores_co_gi_dau():
    result = correct_text("co gi dau")
    assert result.corrected_text == "có gì đâu"
```

```python
def test_phrase_span_restores_ma_tuy():
    result = correct_text("ma tuy")
    assert result.corrected_text == "ma túy"
```

---

## Task 9.2: Add negative/safety tests

* [ ] Add:

```python
def test_phrase_span_does_not_restore_single_ambiguous_ma():
    result = correct_text("ma")
    assert result.corrected_text == "ma"
```

```python
def test_phrase_span_does_not_corrupt_iphone():
    result = correct_text("iphone")
    assert result.corrected_text.lower() == "iphone"
```

```python
def test_phrase_span_does_not_corrupt_facebook():
    result = correct_text("facebook ban hang")
    assert "facebook" in result.corrected_text.lower()
```

```python
def test_phrase_span_does_not_force_iphone_moi_ra():
    result = correct_text("iphone moi ra")
    assert "iphone" in result.corrected_text.lower()
```

```python
def test_phrase_span_does_not_overcorrect_anh_em_without_context():
    result = correct_text("anh em")
    assert result.corrected_text == "anh em"
```

```python
def test_phrase_span_does_not_blindly_choose_ban_an():
    result = correct_text("ban an")
    # Until we have stronger context/phrase disambiguation,
    # avoid blindly choosing "bàn ăn" or "bạn ăn".
    assert result.corrected_text == "ban an"
```

---

## Task 9.3: Add spacing preservation test

Choose policy.

If spacing should be preserved:

```python
def test_phrase_span_preserves_internal_spacing():
    result = correct_text("vay   thi")
    assert result.corrected_text == "vậy   thì"
```

If spacing normalization is acceptable, explicitly test that instead:

```python
def test_phrase_span_normalizes_internal_spacing():
    result = correct_text("vay   thi")
    assert result.corrected_text == "vậy thì"
```

Do not leave this behavior undefined.

---

## Task 9.4: Run acceptance tests

```bash
pytest tests/stage5_scorer/test_acceptance.py -v -k "phrase_span or ma_tuy or iphone or facebook or ban_an"
```

* [ ] Commit:

```bash
git add tests/stage5_scorer/test_acceptance.py
git commit -m "test: add M6.1 phrase-span restoration acceptance tests"
```

---

# Chunk 10: Debugging / Explainability

## Task 10.1: Add debug metadata

Phrase-span corrections should explain:

```text
- original span
- selected phrase
- score
- risk
- phrase source
- reason accepted/rejected
```

Add metadata in debug mode:

```python
metadata["phrase_span"] = {
    "enabled": True,
    "num_islands": len(islands),
    "num_phrase_edges": len(phrase_edges),
    "accepted_edges": [...],
    "rejected_edges": [...],
}
```

For accepted edge:

```json
{
  "original": "vay thi gio phai lam the nao",
  "replacement": "vậy thì giờ phải làm thế nào",
  "score": 5.1975,
  "risk": 0.01,
  "source": "phrase_span",
  "phrase_id": "phrase/..."
}
```

* [ ] Add tests if existing debug-output tests exist.

* [ ] Commit:

```bash
git add src tests
git commit -m "feat: add phrase-span debug metadata"
```

---

# Chunk 11: Final Verification

* [ ] Run full quality suite:

```bash
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```

* [ ] Run CLI smoke tests:

```bash
corrector --json "vay thi gio phai lam the nao ???"
corrector --json "moi quan he"
corrector --json "ma"
corrector --json "iphone moi ra"
```

Expected:

```text
vay thi gio phai lam the nao ??? -> vậy thì giờ phải làm thế nào ???
moi quan he -> mối quan hệ
ma -> ma
iphone moi ra -> iphone moi ra or iphone mới ra only if existing non-phrase logic safely supports it
```

* [ ] If needed, commit final fixes:

```bash
git add -A
git commit -m "fix: address M6.1 phrase-span restoration verification issues"
```

---

# Non-Goals

M6.1 should **not** do these:

```text
- Do not implement broad no-tone n-gram scoring as the primary fix.
- Do not globally reduce edit-distance penalty.
- Do not broadly weaken overcorrection penalty.
- Do not add ML dependencies.
- Do not attempt full sentence-level language modeling.
- Do not autocorrect single-token ambiguous no-tone forms like "ma".
```

---

# Definition of Done

* `lookup_phrase_notone()` exists and returns all phrase entries for a no-tone key.
* `LexiconDataStore` builds a no-tone phrase index from JSON/SQLite phrase sources.
* Word islands are extracted from raw tokens, preserving raw token and char spans.
* Phrase-span proposer generates safe phrase edges over word-island positions.
* Lattice decoder uses Viterbi-style DP over word positions.
* Lattice edges include score, risk, source, raw span, char span, and explanation.
* Phrase-span decode result is accepted only through margin + risk gate.
* Phrase-span changes merge safely with existing accepted changes.
* Positive acceptance cases pass:

  * `vay thi gio phai lam the nao ??? -> vậy thì giờ phải làm thế nào ???`
  * `moi quan he -> mối quan hệ`
  * `quan he -> quan hệ`
  * `lam the nao -> làm thế nào`
  * `khong biet lam sao -> không biết làm sao`
  * `co gi dau -> có gì đâu`
  * `ma tuy -> ma túy`
* Negative cases pass:

  * `ma` unchanged
  * `iphone` unchanged
  * `facebook` not corrupted
  * `anh em` not overcorrected without context
  * `ban an` not blindly disambiguated
* Debug metadata explains phrase-span decisions.
* Full quality suite passes:

  * `ruff check src tests`
  * `ruff format --check src tests`
  * `mypy src tests`
  * `pytest`

```

