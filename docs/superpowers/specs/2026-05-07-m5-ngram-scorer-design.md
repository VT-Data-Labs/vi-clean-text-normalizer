# M5 — N-Gram Phrase Scorer Design

## Purpose

M5 is the first **context-aware ranking layer** for the Vietnamese correction pipeline. It scores candidate sequences inside a small local window using n-gram phrase evidence, domain context, OCR confusion support, and overcorrection prevention.

M5 does not make final correction decisions — it produces ranked `ScoredSequence` objects with score breakdown and explanation. M6 (Decision Engine) consumes these later.

## Package Structure

```
src/vn_corrector/stage5_scorer/
├── __init__.py
├── config.py
├── weights.py
├── types.py
├── ngram_store.py          # ABC interface
├── domain_context.py
├── windowing.py
├── combinations.py
├── scorer.py
├── explain.py
├── diagnostics.py
├── backends/
│   ├── __init__.py
│   └── json_ngram_store.py # concrete ABC impl

tests/stage5_scorer/
├── test_types.py
├── test_ngram_store.py
├── test_domain_context.py
├── test_windowing.py
├── test_combinations.py
├── test_scorer.py
├── test_explain.py
└── test_acceptance.py

resources/
├── phrases/
│   ├── phrases.vi.json
│   ├── negative_phrases.vi.json
│   └── domains/
│       └── product_instruction.vi.json
└── ngrams/
    └── ngram_store.vi.json

scripts/
└── build_ngram_store.py
```

## Data Flow

```
M4 TokenCandidates[]
      ↓
windowing.py — build CandidateWindow around ambiguous tokens
      ↓
combinations.py — generate CandidateSequence permutations
      ↓
scorer.py — score each sequence against 8 scoring signals
      ↓
ScoredSequence[] — ranked list with ScoreBreakdown + evidence
```

## Core Types

### `config.py`

```python
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

### `weights.py`

```python
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

### `types.py`

```python
@dataclass(frozen=True)
class ScoreBreakdown:
    word_validity: float = 0.0
    syllable_freq: float = 0.0
    phrase_ngram: float = 0.0
    domain_context: float = 0.0
    ocr_confusion: float = 0.0
    edit_distance: float = 0.0
    overcorrection_penalty: float = 0.0   # stored positive, subtracted in total
    negative_phrase_penalty: float = 0.0  # stored positive, subtracted in total

    @property
    def total(self) -> float:
        additions = (
            self.word_validity
            + self.syllable_freq
            + self.phrase_ngram
            + self.domain_context
            + self.ocr_confusion
            + self.edit_distance
        )
        penalties = self.overcorrection_penalty + self.negative_phrase_penalty
        return additions - penalties


@dataclass(frozen=True)
class CandidateWindow:
    start: int
    end: int
    token_candidates: list[TokenCandidates]  # concrete type from M4


@dataclass(frozen=True)
class CandidateSequence:
    tokens: tuple[str, ...]
    original_tokens: tuple[str, ...]
    changed_positions: tuple[int, ...]


@dataclass(frozen=True)
class CorrectionEvidence:
    kind: str
    message: str
    score_delta: float = 0.0
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)


@dataclass(frozen=True)
class TokenCorrectionExplanation:
    index: int
    original: str
    corrected: str
    evidence: list[CorrectionEvidence]


@dataclass(frozen=True)
class ScoredSequence:
    sequence: CandidateSequence
    breakdown: ScoreBreakdown
    confidence: float
    explanations: list[TokenCorrectionExplanation] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.breakdown.total


@dataclass(frozen=True)
class ScoredWindow:
    window: CandidateWindow
    ranked_sequences: list[ScoredSequence]

    @property
    def best(self) -> ScoredSequence | None:
        return self.ranked_sequences[0] if self.ranked_sequences else None
```

## NgramStore Interface (ABC)

```python
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

Missing phrases return `0.0` — never raise.

### JsonNgramStore

Concrete backend. Loads from `resources/ngrams/ngram_store.vi.json`. Supports bigrams, trigrams, fourgrams, domain phrases, and negative phrases.

## Windowing

`windowing.py` builds local windows around tokens with >1 candidate:

- For each ambiguous token, create window `[index - 3, index + 4)`
- Merge overlapping windows
- Clamp to `max_tokens_per_window = 7`
- Preserve original token positions

## Combination Generation

`combinations.py` generates candidate sequences from a window:

- Always include the identity path (all original tokens)
- Limit per-token candidates to `max_candidates_per_token`
- Never generate more than `max_combinations = 5000`
- When trimming, never drop the original candidate
- Deterministic ordering

## Scoring Formula

```
score =
  word_validity
  + syllable_freq
  + phrase_ngram
  + domain_context
  + ocr_confusion
  + edit_distance
  - overcorrection_penalty
  - negative_phrase_penalty
```

Each component is a private method on `PhraseScorer`:

| Method | Input | Description |
|--------|-------|-------------|
| `_score_word_validity` | token text → lex lookup | +1.0 per token found in lexicon |
| `_score_syllable_freq` | token text → lex freq | from `LexiconEntry.score.frequency` |
| `_score_phrase_ngram` | sequence → ngram store | bigram/trigram/fourgram weighted sum |
| `_score_domain_context` | domain + sequence | from domain_phrases section |
| `_score_ocr_confusion` | token text → lex lookup | from `OcrConfusionEntry` |
| `_score_edit_distance` | M4 `Candidate.edit_distance` | `1.0 / (1.0 + dist)` formula |
| `_score_overcorrection_penalty` | all valid tokens changed | penalizes unnecessary changes |
| `_score_negative_phrase_penalty` | sequence → ngram store | penalizes known-bad sequences |

## Diagnostics

`diagnostics.py` exposes debug output for human review:

```python
def format_scored_window(window: ScoredWindow, top_k: int = 5) -> str: ...
```

Returns a human-readable string showing:
- Window position (start, end) and token texts
- Top-K ranked sequences with their `ScoreBreakdown`
- Markers for which sequences differ from the original
- Key evidence items for changed tokens

Designed for CLI debug and development inspection, not for production output.

## Data Loading Strategy

The build script (`scripts/build_ngram_store.py`) reads:
- `resources/phrases/phrases.vi.json` (curated positive phrases)
- `resources/phrases/negative_phrases.vi.json` (known-bad sequences)
- `resources/phrases/domains/*.vi.json` (domain-specific phrases)

...and merges them into a single generated file `resources/ngrams/ngram_store.vi.json`.

`JsonNgramStore` loads **only** `ngram_store.vi.json` — it does not load individual phrase files. This keeps the runtime simple: one file, one load, all data pre-merged.

## Overcorrection Penalty

Applied when every non-protected token in a window matches the original text but the sequence was changed anyway. The penalty is proportional to the fraction of valid-original tokens that were modified:

```
overcorrection_penalty = weight * (changed_valid_tokens / total_changeable_tokens)
```

Where `changed_valid_tokens` counts tokens that were valid Vietnamese words AND were changed. This penalizes rewriting valid text without strong compensating evidence.

## Explainability

Every `ScoredSequence` carries `ScoreBreakdown` and per-token `TokenCorrectionExplanation` for changed tokens. Evidence entries record `kind`, `message`, `score_delta`, and optional `metadata` — all JSON-serializable.

## Acceptance Criteria

1. `số mùông gạt ngang` → `số muỗng gạt ngang` ranked highest
2. `lâm người nhanh` + domain=`product_instruction` → `làm nguội nhanh` ranked highest; without domain → not aggressively corrected
3. Missing phrase data → no crash, `phrase_ngram=0`, `domain_context=0`
4. Combination generation never exceeds `max_combinations`
5. Every changed token has explainable evidence
6. Tests assert relative ranking, not exact floats

## What M5 Does NOT Do

- Make final correction decisions (deferred to M6)
- Require large corpus statistics
- Hardcode per-token correction rules
- Refactor M4 types

## Phases

| Phase | Deliverables | Done When |
|-------|-------------|-----------|
| M5.1 | Skeleton: config, weights, types, `__init__.py` | Unit tests pass for types |
| M5.2 | Phrase datasets + ngram builder script | `ngram_store.vi.json` generated |
| M5.3 | `NgramStore` ABC + `JsonNgramStore` | All score methods return `float`, missing returns `0.0` |
| M5.4 | Windowing | Windows built around ambiguous tokens, max length enforced |
| M5.5 | Combination generator | Identity path preserved, limits respected |
| M5.6 | PhraseScorer with all 8 scoring signals | All acceptance tests pass |
| M5.7 | Explain + diagnostics | Every changed token explainable; diagnostics module exposes `format_scored_window(w)` for debug output |
| M5.8 | Integration with M4 | `stage5_scorer.score_tokens(candidates: list[TokenCandidates]) → list[ScoredWindow]` entry point works with M4 output |
