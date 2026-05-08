# M6.1: Phrase-Span Lattice Decoder for No-Tone Vietnamese Restoration

## Problem

Accent restoration is still mostly token-local plus sequence scoring. This fails for inputs where evidence only appears after multiple adjacent tokens are corrected together.

Example: `vay thi gio phai lam the nao ???` should become `vậy thì giờ phải làm thế nào ???`, but the current scorer never discovers this path because n-gram evidence (e.g. `vậy thì`) only fires when both adjacent tokens are already corrected.

## Solution: Phrase-Span Lattice Decoder

Treat accent restoration as structured sequence decoding:

```
candidate lattice
→ phrase/span proposal edges
→ Viterbi decoding
→ safety decision gate
→ explainable correction result
```

## Modules

### 1. No-Tone Phrase Index (`data_store.py`)

Add `_notone_phrase_index: dict[str, list[PhraseEntry]]` to `LexiconDataStore`.

Populated from:
- `lexicon_phrases` SQLite table (already has `phrase`, `normalized`, `n`, `freq`, `domain`)
- Stored under `strip_accents(phrase).lower()` as key

New interface method on `LexiconStoreInterface`:
```python
def lookup_phrase_notone(self, no_tone_key: str) -> list[PhraseEntry]: ...
```

### 2. Phrase-Span Proposer (`stage4_candidates/phrase_span.py`)

Scans a token window and generates phrase-span candidate edges.

```python
@dataclass(frozen=True)
class PhraseSpanEdge:
    start: int       # token index
    end: int         # token index (exclusive)
    output_tokens: tuple[str, ...]
    score: float
    phrase: PhraseEntry
```

Algorithm:
- Scan windows of length 2..8
- Filter to word-like tokens only (VI_WORD, FOREIGN_WORD, UNKNOWN)
- Generate no-tone key from span text
- Look up in `_notone_phrase_index`
- Apply safety gates before accepting an edge

### 3. Safety Gates

```python
def is_safe_phrase_restoration(original_span: str, phrase: PhraseEntry) -> bool
```

Conditions:
- `strip_accents(phrase.surface).lower() == strip_accents(original_span).lower()`
- `contains_vietnamese(phrase.surface)` is True
- `contains_vietnamese(original_span)` is False (span is fully accentless)
- phrase has at least 2 tokens
- If phrase source is curated/trusted: `freq >= 0.85`
- Otherwise: `freq >= 0.95` and `num_tokens >= 3`

### 4. Lattice Decoder (`stage5_scorer/lattice.py`)

Viterbi-style dynamic programming over token positions.

```python
@dataclass(frozen=True)
class LatticeEdge:
    start: int
    end: int
    output_tokens: tuple[str, ...]
    score: float
    source: str  # "identity", "single_candidate", "phrase_span"

class LatticeDecoder:
    def decode(self, edges: list[LatticeEdge], n_tokens: int) -> DecodeResult
```

Edge scoring:
```
identity edge:   score = 0
candidate edge:  score = syllable_freq_score + word_validity_score - overcorrection_penalty
phrase edge:     phrase.freq * (3.5 + min(2.0, 0.25 * token_count))
```

### 5. Pipeline Integration

In `pipeline/corrector.py`, after candidate generation and before scoring:
1. Run phrase-span proposal to get `PhraseSpanEdge`s
2. Convert to `LatticeEdge`s
3. Build identity and single-candidate edges from existing candidates
4. Run Viterbi decode
5. Accept phrase-span corrections that pass the safety gate
6. Merge accepted corrections into the scoring window as overrides

## Edge Cases & Safety

- Protected/foreign tokens are never included in phrase spans
- Ambiguous short spans (1-2 tokens with high ambiguity) require phrase evidence
- Existing overcorrection penalty remains for single-token edits
- `iphone`, `facebook`, product codes are never force-accented

## Acceptance Tests

Positive:
- `vay thi gio phai lam the nao ???` → `vậy thì giờ phải làm thế nào ???`
- `moi quan he` → `mối quan hệ`
- `quan he` → `quan hệ`
- `lam the nao` → `làm thế nào`
- `khong biet lam sao` → `không biết làm sao`
- `co gi dau` → `có gì đâu`
- `ma tuy` → `ma túy`

Negative/safety:
- `ma` → unchanged
- `iphone` → unchanged
- `facebook ban hang` → `facebook` unchanged
- `anh em` → unchanged (no strong phrase context)
- `ban an` → unchanged (ambiguous)
