# Development Guide

This document is for developers contributing to `vi-clean-text-normalizer`. For user-facing documentation (installation, quick start, CLI, API), see [README.md](README.md).

---

## Table of Contents

- [Architecture](#architecture)
- [Package structure](#package-structure)
- [Resource files](#resource-files)
- [Development setup](#development-setup)
- [Code quality](#code-quality)
- [Testing](#testing)
- [Running CI checks](#running-ci-checks)
- [Milestone roadmap](#milestone-roadmap)
- [Coding rules](#coding-rules)

---

## Architecture

The full pipeline:

```text
OCR Raw Text
  ↓
Stage 0: Input Normalization
  ↓
Stage 1: Unicode Normalization       ← implemented
  ↓
Stage 2: Case Masking                ← implemented
  ↓
Stage 3: Protected Token Detection   ← implemented
  ↓
Stage 4: Tokenization                ← implemented
  ↓
Stage 5: Candidate Generation        ← implemented
  ↓
Stage 6: Candidate Scoring           ← implemented (M5)
  ↓
Stage 7: Correction Decision         ← implemented (M6)
  ↓
Stage 8: Case Restoration            ← implemented
  ↓
Stage 9: Output + Change Log + Flags
  ↓
Evaluation: Gold data → metrics → report  ← implemented (M7)
```

### Pipeline orchestration

The M6.5 pipeline (`vn_corrector.pipeline`) wires Stages 1–6 into a single `correct_text()` entry point:

```text
raw text
  → normalize (Stage 1)
  → protect spans (Stage 3)
  → tokenize (Stage 4)
  → generate candidates (Stage 4)
  → build candidate windows (Stage 5)
  → score windows (Stage 5)
  → decide correction (Stage 6)
  → reconstruct text
  → return CorrectionResult
```

Use `TextCorrector` in production to avoid reloading the lexicon and scorer on every call. The module-level `correct_text()` function caches a default `TextCorrector` via `lru_cache`.

---

## Package structure

```text
src/vn_corrector/
├── __init__.py               # Exports correct_text
├── cli.py                    # CLI entrypoint + subcommands
├── normalizer.py             # Re-exports from stage1_normalize
├── case_mask.py              # Case detection and restoration
├── tokenizer.py              # Tokenization with roundtrip guarantee
├── protected_tokens.py       # Re-exports from stage3_protect
├── pipeline/                 # M6.5 — Production pipeline orchestration
│   ├── __init__.py
│   ├── config.py             # PipelineConfig (frozen dataclass)
│   ├── context.py            # PipelineContext + dependency loading
│   ├── corrector.py          # TextCorrector + correct_text
│   ├── reconstruction.py     # Offset-based text reconstruction
│   ├── diagnostics.py        # Debug output formatters
│   └── errors.py             # PipelineError hierarchy
├── common/
│   ├── enums.py              # Pipeline-wide enums
│   ├── spans.py              # TextSpan, ProtectedSpan, Token, CaseMask
│   ├── scoring.py            # Score, ScoreBreakdown
│   ├── correction.py         # CorrectionDecision, Change, Flag, Result
│   ├── contracts.py          # M4→M5→M6 DTOs
│   ├── constants.py          # Thresholds and weights
│   ├── lexicon.py            # LexiconStoreInterface ABC
│   ├── errors.py             # Custom error types
│   ├── types.py              # Deprecated backward-compat re-exports
│   └── validation.py         # Lexicon entry validation
├── utils/
│   └── unicode.py            # Vietnamese character detection
├── stage1_normalize/         # Unicode normalization engine
├── stage2_lexicon/           # Lexicon store + build pipeline
├── stage3_protect/           # Protected token detection
├── stage4_candidates/        # Candidate generation (8 sources)
├── stage5_scorer/            # N-gram phrase scoring
├── stage6_decision/          # Decision engine
└── stage7_evaluation/        # Evaluation harness
```

---

## Resource files

```text
resources/
├── lexicons/                 # Built-in JSON lexicon data
│   ├── syllables.vi.json     # 7,400+ Vietnamese syllable forms
│   ├── words.vi.json         # Common Vietnamese words
│   ├── phrases.vi.json       # Multi-word phrases
│   ├── units.vi.json         # Measurement units
│   ├── abbreviations.vi.json
│   ├── foreign_words.json    # Chemical/brand domain terms
│   ├── ocr_confusions.vi.json  # Known OCR error patterns
│   └── chemicals.txt
├── ngrams/
│   └── ngram_store.vi.json   # Merged bigrams/trigrams/fourgrams
├── matchers/                  # YAML matcher configs (URL, email, phone, etc.)
data/lexicon/
    └── trusted_lexicon.db    # SQLite DB (built by build_trusted_lexicon_db.py)
```

---

## Development setup

```bash
# Clone and install with dev dependencies
git clone https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer.git
cd vi-clean-text-normalizer
uv sync --all-extras

# Build the SQLite lexicon DB (optional, needed for sqlite/hybrid backends)
python scripts/build_trusted_words_vi.py --output data/lexicon/trusted_words.jsonl
python scripts/build_trusted_lexicon_db.py \
    --resources resources/lexicons \
    --trusted-jsonl data/lexicon/trusted_words.jsonl \
    --output data/lexicon/trusted_lexicon.db
```

---

## Code quality

### Lint and format

```bash
ruff check src tests
ruff format --check src tests
```

Auto-fix:

```bash
ruff format src tests
ruff check --fix src tests
```

### Type checking

```bash
mypy src tests
```

All code MUST be fully typed — no `Any`, no `object`, no `# type: ignore` comments.

### Testing

```bash
# Full suite (1059+ tests)
pytest

# With coverage
pytest --cov=vn_corrector --cov-report=term-missing

# Specific areas
pytest tests/pipeline/
pytest tests/stage4_candidates/
pytest tests/test_normalizer.py
```

### Pre-commit

```bash
pre-commit run --all-files
```

CI runs in this order: `ruff check` → `ruff format --check` → `mypy` → `pytest`.

---

## Running CI checks

```bash
# Full verification (matches CI pipeline)
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```

---

## Milestone roadmap

### ✅ M1 — Basic Normalization
- Unicode normalizer (NFC, control chars, whitespace)
- Case masker (UPPER/LOWER/TITLE/MIXED/UNKNOWN)
- Tokenizer with roundtrip guarantee

### ✅ M2 — Lexicon Store
- Backend-agnostic `LexiconStoreInterface` ABC
- `JsonLexiconStore`, `SqliteLexiconStore`, `HybridLexiconStore`
- Lexicon build pipeline + trusted-lexicon generator

### ✅ M3 — Protected Token Detection
- Regex and lexicon matchers (URL, email, phone, codes, chemicals)
- Priority-based conflict resolution
- Mask/restore roundtrip with placeholder tracking
- YAML-configurable matcher registry

### ✅ M4 — Candidate Generation
- 8 source generators (original, syllable map, OCR confusion, word lexicon, abbreviation, phrase evidence, edit distance, domain-specific)
- Deterministic ranking, LRU cache, limit enforcement
- Diagnostics, real-lexicon golden YAML tests

### ✅ M5 — N-Gram Phrase Scorer
- `PhraseScorer` with 8 deterministic signals
- Bounded windowing + combinatorial sequence generation
- Per-token `CorrectionEvidence` with score deltas

### ✅ M6 — Decision Engine
- Confidence and margin calculation
- Replace / keep / flag decisions
- `CorrectionDecision`, `CorrectionChange`, `CorrectionFlag`

### ✅ M6.5 — Production Pipeline Integration
- `PipelineConfig`, `PipelineContext`, `TextCorrector`, `correct_text()`
- End-to-end wiring of Stages 1–6
- Offset-based reconstruction, overlap resolution, fail-closed safety
- CLI delegates to pipeline

### ✅ M6.1 — Phrase-Span Lattice Decoder
- Safety-gated phrase-span proposer (`PhraseSpanProposer`)
- Viterbi decoder (`LatticeDecoder`) over word-position lattice edges
- Phrase-edge scoring with length bonus and risk adjustment
- Safe-restoration gate (accentless → accented only; minimum phrase length and confidence)
- Integration with candidate generation and scoring pipelines

### ✅ M7 — Evaluation Harness
- Gold test set format (JSONL)
- CER / WER / precision / recall / overcorrection rate
- `scripts/evaluate.py` runner

### M8 — Feedback Loop
- [ ] Correction logging format
- [ ] Human accepted/rejected labels
- [ ] Confusion map update script

---

## Coding rules

### General

- **DRY — Do Not Repeat Yourself.** Build a single canonical implementation, import it everywhere.
- **Use abstract base classes (ABC), never `Protocol`** — shared interfaces must inherit from `ABC` with `@abstractmethod`.
- **No `Any` or `object` as type annotations** — use concrete types, generic types, or union types.
- **No `# type: ignore` or `# noqa` suppression comments** — fix the underlying issue instead.
- Prefer modifying existing modules over creating new ones.
- Keep diffs small and reviewable.

### Vietnamese character normalization — single source of truth

All accent stripping, lookalike fixing, and text normalisation lives exclusively in `src/vn_corrector/stage1_normalize/char_normalizer.py`. New code must import from `vn_corrector.stage1_normalize`, never create standalone copies.

### Shared module locations

| Concern | Location |
|---|---|
| Vietnamese char normalization | `stage1_normalize/char_normalizer.py` |
| Stage 1 pipeline | `stage1_normalize/engine.py` |
| Shared constants | `common/constants.py` |
| Shared errors | `common/errors.py` |
| Shared types | `common/enums.py`, `common/spans.py`, `common/scoring.py`, `common/correction.py`, `common/contracts.py`, `common/lexicon.py` |
| Shared validation | `common/validation.py` |

### Pipeline conventions

- `PipelineConfig` is a frozen dataclass — all pipeline options in one place.
- Dependencies are loaded once in `PipelineContext` and reused.
- The pipeline fails closed by default: errors return original text with a flag rather than crashing.
- Changes use character-offset `TextSpan` for faithful reconstruction.
- Protected tokens receive only identity candidates — never corrected.

---

For a higher-level overview of project goals, non-goals, and design philosophy, see [PROJECT.md](PROJECT.md).
