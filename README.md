# vi-clean-text-normalizer

> Vietnamese OCR post-correction engine — conservative, explainable, and safe.

[![Python versions](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![CI](https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-pytest-blue.svg)](#testing)
[![Lint](https://img.shields.io/badge/lint-ruff-purple.svg)](#code-quality)
[![Type Checked](https://img.shields.io/badge/type--checked-mypy-blue.svg)](#code-quality)
[![License](https://img.shields.io/github/license/Vi-Lang-Foundation/vi-clean-text-normalizer.svg)](LICENSE)
[![codecov](https://img.shields.io/codecov/c/github/Vi-Lang-Foundation/vi-clean-text-normalizer)](https://codecov.io/gh/Vi-Lang-Foundation/vi-clean-text-normalizer)
[![Codacy](https://app.codacy.com/project/badge/Grade/99d5369ee6f84e70bbdd16eb345d1c98)](https://app.codacy.com/gh/Vi-Lang-Foundation/vi-clean-text-normalizer/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

---

## Overview

`vi-clean-text-normalizer` is a deterministic, production-grade pipeline for repairing common Vietnamese OCR errors. It corrects tone-marking mistakes, uppercase diacritic errors, and character confusions while preserving the original meaning, layout-sensitive tokens, foreign terms, product codes, numbers, units, and domain-specific vocabulary.

The engine is designed to be **conservative by default** — when uncertain, it keeps the original text and flags the ambiguity rather than hallucinating a correction.

Primary use cases:

- Vietnamese OCR post-processing
- Vietnamese diacritic restoration
- Uppercase Vietnamese correction
- Product label / instruction text correction
- Mixed Vietnamese + English + chemical + numeric text correction

---

## Project Status

> **Status:** ✅ Milestone 5 complete — n-gram phrase scorer with deterministic context-aware ranking

### Implemented

- [x] Unicode normalization (NFC, invisible character removal, whitespace normalization)
- [x] Case masking and restoration (UPPER / LOWER / TITLE / MIXED / UNKNOWN)
- [x] Tokenization with roundtrip reconstruction guarantee
- [x] Protected token detection (URL, email, phone, number, unit, money, percent, code, date, chemical terms)
- [x] Regex and lexicon-based matchers with conflict resolution
- [x] Backend-agnostic lexicon store (`LexiconStoreInterface` ABC — JSON + SQLite + Hybrid)
- [x] Built-in JSON resources (syllables, words, units, phrases, abbreviations, OCR confusions, foreign terms)
- [x] Lexicon build pipeline (syllable, word, phrase, confusion, abbreviation builders)
- [x] Vietnamese accent stripper for lookup key generation
- [x] Shared types, constants, validation, and error enums
- [x] Candidate generation (8 source generators, merging, ranking, limit enforcement, LRU cache)
- [x] Real-lexicon acceptance tests + golden YAML regression suite
- [x] Benchmark script and debug CLI
- [x] CLI entrypoint (correction + lexicon + candidates subcommands)
- [x] CI pipeline (pytest + ruff + mypy + pre-commit)
- [x] **N-gram phrase scoring** — `PhraseScorer` with 8 deterministic signals (word validity, syllable freq, phrase n-gram, domain context, OCR confusion, edit distance, overcorrection penalty, negative phrase penalty)
- [x] **Context-aware windowing** — bounded sliding windows around ambiguous tokens with merging
- [x] **Candidate sequence ranking** — combinatorial generation with identity-path preservation and max-combination limits
- [x] **Explainability** — per-token `CorrectionEvidence` with score deltas and JSON-serializable breakdowns
- [x] **Curated phrase dataset** — `resources/phrases/` with 11 positive phrases, 3 negative phrases, and domain-specific entries
- [x] **NgramStore ABC** — `JsonNgramStore` backend, `scripts/build_ngram_store.py` builder
- [x] 949+ tests across 24 test files

### Known Limitations

- APIs may change before `v1.0.0`.
- Correction logic beyond basic normalization and protected token masking is not yet wired.
- See [PROJECT.md](PROJECT.md) for the full roadmap.

### In Progress

- [ ] Full correction pipeline (Stages 7–9)
- [ ] Decision engine
- [ ] Evaluation harness
- [ ] PyPI release

---

## Features

- **Unicode normalization** — NFC composition, invisible/control character removal, whitespace normalization (preserving intentional newlines, tabs, CR)
- **Case masking** — detect case patterns (UPPER/LOWER/TITLE/MIXED/UNKNOWN), produce lowercase working copies, restore original casing after correction
- **Tokenization** — fine-grained token splitting with strict roundtrip guarantee: `reconstruct(tokenize(text)) == text`
- **Protected token detection** — regex and lexicon matchers for URLs, emails, phone numbers, numbers, units, money, percentages, codes, dates, chemical terms; conflict resolution with priority-based ranking
- **Vietnamese detection** — correct identification of Vietnamese characters with tone marks across Unicode blocks
- **Lexicon store** — pluggable backend architecture (ABC + JSON + SQLite + Hybrid), accent-insensitive lookups, syllable candidates, phrase matching, OCR confusion resolution
- **Three explicit backends** — `JsonLexiconStore` (JSON resources only), `SqliteLexiconStore` (SQLite DB only), `HybridLexiconStore` (primary/fallback composition)
- **Lexicon build pipeline** — `build_trusted_lexicon.py` generates trusted-word JSONL; `build_lexicon_db.py` compiles JSON resources + trusted JSONL into a single SQLite runtime DB
- **SQLite backend** — query-based store using stdlib `sqlite3`, loads pre-built DB via `SqliteLexiconStore.from_db()`
- **Candidate generation** — 8 source generators (original, syllable map, OCR confusion, word lexicon, abbreviation, phrase evidence, edit distance, domain-specific), deterministic ranking, limit enforcement, token cache
- **N-gram phrase scoring** — `PhraseScorer` with 8 deterministic signals (word validity, syllable freq, phrase n-gram, domain context, OCR confusion, edit distance, overcorrection penalty, negative phrase penalty), bounded windowing around ambiguous tokens, combinatorial sequence generation with identity-path preservation
- **Explainability** — per-token `CorrectionEvidence` with score deltas, `ScoreBreakdown` with `total()` property, `format_explanation()` and `format_scored_window()` debug output
- **Curated phrase data** — `resources/phrases/` with 11 positive phrases, 3 negative phrases, domain-specific entries; `scripts/build_ngram_store.py` builder generates a single merged `resources/ngrams/ngram_store.vi.json`
- **CLI interface** — single-text, batch file, interactive, JSON output modes, plus dedicated subcommands: `lexicon` (info, lookup, candidates, validate) and `candidates` (debug candidate view)
- **Benchmark script** — `scripts/bench_stage4_candidates.py` for token/sec, cache efficiency, candidate distribution

---

## Installation

### From source

```bash
git clone https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer.git
cd vi-clean-text-normalizer
uv sync
```

### Development install

```bash
uv sync --all-extras
```

---

## Quick Start

```python
from vn_corrector.normalizer import normalize

text = "RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ"
result = normalize(text)

print(result)  # "RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ"
```

```python
from vn_corrector.tokenizer import tokenize, reconstruct

tokens = tokenize("SỐ MÙÔNG (GẠT NGANG)")
reconstructed = reconstruct(tokens)

assert reconstructed == "SỐ MÙÔNG (GẠT NGANG)"  # roundtrip guarantee
```

```python
from vn_corrector.protected_tokens import protect

doc = protect("Liên hệ support@example.com hoặc gọi 1900-1009")
# doc.masked_text: "Liên hệ <<EMAIL_0>> hoặc gọi <<PHONE_0>>"
# doc.spans: [Span(type=EMAIL, ...), Span(type=PHONE, ...)]
```

---

## CLI Usage

The CLI is available as `corrector` (installed via `uv sync`):

```bash
uv run corrector "SỐ MÙÔNG (GẠT NGANG)"
```

Output:

```
Original:  SỐ MÙÔNG (GẠT NGANG)
Corrected: SỐ MÙÔNG (GẠT NGANG)
Confidence: 100.00%
```

(Full correction pipeline is in development — currently runs Stage 0 normalization only.)

### Lexicon subcommands

The `corrector lexicon` subcommand group provides inspection tools:

```bash
# Show lexicon statistics (JSON backend)
uv run corrector lexicon info

# SQLite backend
uv run corrector --lexicon-mode sqlite --lexicon-db data/lexicon/trusted_lexicon.db lexicon info

# Hybrid backend (SQLite primary, JSON fallback)
uv run corrector --lexicon-mode hybrid --lexicon-db data/lexicon/trusted_lexicon.db lexicon info

# Look up a word across all indexes
uv run corrector lexicon lookup "muỗng"
uv run corrector lexicon lookup "kg"

# Show syllable candidates for a no-tone key
uv run corrector lexicon candidates muong

# Validate all built-in lexicon resource files
uv run corrector lexicon validate
```

### Candidate debug subcommand

The `candidates` subcommand shows per-token candidate tables with sources and evidence:

```bash
# Show candidate debug view
uv run corrector candidates "người đẫn đường"
```

Output:

```text
Input text: 'người đẫn đường'
Tokens: 3

Token[0] người
  - người          prior=0.100  [original] (original)
      evidence: [original] identity_candidate

Token[1] đẫn
  - đẫn            prior=0.100  [original] (original)
      evidence: [original] identity_candidate
  - dẫn            prior=0.500  [ocr_confusion, syllable_map]
      evidence: [ocr_confusion] ocr_confusion: đẫn -> dẫn
      evidence: [syllable_map] no_tone_key=dan
  - dần            prior=0.200  [syllable_map]
      evidence: [syllable_map] no_tone_key=dan
```

### Benchmark script

```bash
uv run python scripts/bench_stage4_candidates.py --tokens 5000 --cache
```

Output:

```text
Tokens: 5000
Cache:  enabled
...
Tokens/sec:  ~15000
Avg candidates:  ~2.3
```

### Batch and JSON modes

```bash
# Read from file
uv run corrector < input.txt

# JSON output
uv run corrector --json "input text"

# Interactive mode
uv run corrector --interactive
```

### CLI options

| Flag | Description |
|------|-------------|
| `--domain` | Domain context (e.g., `milk_instruction`) |
| `--json` | Output raw JSON |
| `--interactive`, `-i` | Interactive line-by-line mode |
| `--pipeline` | Pipeline stage: `stage0` (default) or `full` (future) |

Lexicon subcommands also support:

| Flag | Description |
|------|-------------|
| `--lexicon-mode` | Backend: `json` (default), `sqlite`, or `hybrid` |
| `--lexicon-db` | Path to SQLite DB (for sqlite/hybrid modes) |

---

## Python API

### Basic normalization

```python
from vn_corrector.normalizer import normalize

normalize("RỐT NƯỚC")  # Unicode + whitespace normalization
```

### Case masking

```python
from vn_corrector.case_mask import create_case_mask, apply_case_mask

mask = create_case_mask("RỐT")          # CaseMask(original="RỐT", working="rốt", case_pattern="UPPER")
result = apply_case_mask("rót", mask)  # "RÓT"
```

### Tokenization

```python
from vn_corrector.tokenizer import tokenize, reconstruct

tokens = tokenize("SỐ MÙÔNG (GẠT NGANG)")
# Tokens: [VI_WORD("SỐ"), SPACE(" "), VI_WORD("MÙÔNG"), SPACE(" "),
#          PUNCT("("), VI_WORD("GẠT"), SPACE(" "), VI_WORD("NGANG"), PUNCT(")")]

text = reconstruct(tokens)  # "SỐ MÙÔNG (GẠT NGANG)"
```

### Protected tokens

```python
from vn_corrector.protected_tokens import protect

# Auto-detect and mask protected spans
doc = protect("Mua 2 hộp sữa, giá 450.000đ, giao tại 12 Nguyễn Huệ")
# doc.masked_text: "Mua <<NUMBER_0>> hộp sữa, giá <<MONEY_0>>, giao tại <<NUMBER_1>> Nguyễn Huệ"
```

### Lexicon store

```python
from vn_corrector.stage2_lexicon import load_default_lexicon, HybridLexiconStore

# JSON resources only (small human-curated seed data)
store = load_default_lexicon("json")  # returns JsonLexiconStore

# SQLite production backend (requires pre-built DB)
store = load_default_lexicon("sqlite", db_path="data/lexicon/trusted_lexicon.db")

# Hybrid: SQLite primary, JSON fallback
store = load_default_lexicon("hybrid", db_path="data/lexicon/trusted_lexicon.db")
```

Or construct backends directly:

```python
from vn_corrector.stage2_lexicon import JsonLexiconStore
from vn_corrector.stage2_lexicon.backends import SqliteLexiconStore, HybridLexiconStore

# JSON — built-in resources only
json_store = JsonLexiconStore.from_resources()

# SQLite — existing DB
sqlite_store = SqliteLexiconStore.from_db("data/lexicon/trusted_lexicon.db")

# Hybrid — explicit composition
hybrid = HybridLexiconStore(primary=sqlite_store, fallback=json_store)
```

All stores share the same API:

```python
# Syllable candidates (accent-insensitive)
store.get_syllable_candidates("muong")
# → [LexiconEntry(surface="muỗng", ...), LexiconEntry(surface="mường", ...), ...]

# Surface lookup
store.lookup("muỗng")      # LexiconLookupResult(found=True, ...)
store.contains_word("số muỗng")  # True
store.contains_foreign_word("DHA")  # True

# OCR confusion corrections
store.get_ocr_corrections("mùông")  # OcrConfusionLookupResult with Candidate objects

# Phrase matching
store.lookup_phrase_str("so muong gat ngang")  # "số muỗng gạt ngang"
```

#### Building the SQLite database

```bash
# Step 1: Generate trusted-word JSONL from external dictionaries
python scripts/build_trusted_lexicon.py --output data/lexicon/trusted_words.jsonl

# Step 2: Compile JSON resources + trusted JSONL into the official DB
python scripts/build_lexicon_db.py \
    --resources resources/lexicons \
    --trusted-jsonl data/lexicon/trusted_words.jsonl \
    --output data/lexicon/trusted_lexicon.db
```

The output DB uses the official `SqliteLexiconStore` schema and can be loaded at runtime with `SqliteLexiconStore.from_db()` or `load_default_lexicon("sqlite")`.

#### Build pipeline

```text
resources/lexicons/*.json   (human-curated seed data)
         │
         ├──→ build_lexicon_db.py ──→ trusted_lexicon.db ──→ SqliteLexiconStore.from_db()
         │
trusted_words.jsonl         (generated by build_trusted_lexicon.py)
         ↑
external dictionaries / corpus
```

---

## Architecture

The full pipeline (Stages 7–9 in development):

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
Stage 7: Correction Decision         ← not yet implemented
  ↓
Stage 8: Case Restoration            ← implemented
  ↓
Stage 9: Output + Change Log + Flags
```

### Module layout

```text
src/vn_corrector/
├── __init__.py
├── cli.py                   # CLI entrypoint + lexicon subcommands
├── normalizer.py            # Re-exports from stage1_normalize
├── case_mask.py             # Case detection and restoration (Stages 2, 8)
├── tokenizer.py             # Tokenization with roundtrip (Stage 4)
├── protected_tokens.py      # Re-exports from stage3_protect
├── common/
│   ├── constants.py         # Thresholds, weights, pipeline constants
│   ├── errors.py            # Flag types, decision types, case patterns
│   ├── types.py             # Core dataclasses (Token, CaseMask, Span, CorrectionResult, etc.)
│   └── validation.py        # Lexicon entry validation helpers
├── lexicon/
│   ├── __init__.py          # Re-exports: LexiconStore, JsonLexiconStore, SqliteLexiconStore
│   ├── store.py             # LexiconStore ABC + JsonLexiconStore
│   ├── backends.py          # SqliteLexiconStore (stdlib sqlite3)
│   └── accent_stripper.py   # Vietnamese diacritic stripping
├── utils/
│   └── unicode.py           # Vietnamese character detection
├── stage1_normalize/        # Stage 1 — Unicode normalization engine
│   ├── engine.py            # Orchestrates normalization steps
│   ├── config.py            # NormalizerConfig dataclass
│   ├── types.py             # NormalizedDocument dataclass
│   └── steps/
│       ├── unicode.py       # NFC normalization step
│       ├── invisible.py     # Invisible/control character removal
│       └── whitespace.py    # Whitespace normalization
├── stage2_lexicon/          # Lexicon store + build pipeline
│   ├── core/                # ABC, normalize_key, types (LexiconIndex, build types)
│   ├── backends/            # JsonLexiconStore + SqliteLexiconStore + HybridLexiconStore
│   ├── builders/            # Syllable, word, phrase, confusion, abbreviation builders
│   └── pipeline/            # BuildPipeline orchestration + build_all()
└── stage3_protect/          # Stage 3 — Protected token detection
    ├── engine.py            # protect(), mask(), restore(), resolve_conflicts()
    ├── registry.py          # load_matchers() from YAML config files
    └── matchers/
        ├── base.py          # Matcher ABC
        ├── regex.py         # RegexMatcher — pattern-based detection
        └── lexicon.py       # LexiconMatcher — dictionary-based detection
└── stage4_candidates/       # Stage 5 — Candidate generation
    ├── config.py            # CandidateGeneratorConfig
    ├── generator.py         # CandidateGenerator orchestrator
    ├── cache.py             # TokenCache with LRU eviction
    ├── limits.py            # Candidate trimming + window enforcement
    ├── ranking.py           # Deterministic prior-score ranking
    ├── diagnostics.py       # Explainability helpers
    ├── types.py             # Candidate, CandidateContext, CandidateProposal, etc.
    └── sources/             # 8 source generators
        ├── base.py          # CandidateSourceGenerator ABC
        ├── original.py      # Identity / protected bypass
        ├── syllable_map.py  # No-tone key → accented forms
        ├── ocr_confusion.py # OCR confusion replacements
        ├── word_lexicon.py  # Known dictionary words
        ├── abbreviation.py  # Abbreviation expansion
        ├── phrase_evidence.py  # Phrase-context tagging
        ├── edit_distance.py # Controlled approximate matching
        └── domain_specific.py  # Domain-filtered candidates
└── stage5_scorer/           # Stage 6 — N-gram phrase scorer
    ├── config.py            # PhraseScorerConfig
    ├── weights.py           # ScoringWeights dataclass
    ├── types.py             # ScoreBreakdown, CandidateWindow, ScoredSequence, etc.
    ├── ngram_store.py       # NgramStore ABC
    ├── windowing.py         # Bounded window builder around ambiguous tokens
    ├── combinations.py      # Candidate sequence generation with identity preservation
    ├── scorer.py            # PhraseScorer with 8 deterministic signals
    ├── explain.py           # format_explanation() for human-readable output
    ├── diagnostics.py       # format_scored_window() debug output
    └── backends/
        ├── __init__.py
        └── json_ngram_store.py  # JsonNgramStore — loads from resources/ngrams/ngram_store.vi.json
```

### Resource files

```text
resources/
├── lexicons/                # Built-in JSON lexicon data
│   ├── syllables.vi.json    # 7,400+ Vietnamese syllable forms
│   ├── words.vi.json        # Common Vietnamese words
│   ├── phrases.vi.json      # Multi-word phrases with n-gram counts
│   ├── units.vi.json        # Measurement units
│   ├── abbreviations.vi.json
│   ├── foreign_words.json   # Domain terms (chemical, brand, etc.)
│   ├── ocr_confusions.vi.json  # Known OCR error patterns
│   └── chemicals.txt        # Chemical term lexicon
├── phrases/                 # Curated phrase datasets for M5 scorer
│   ├── phrases.vi.json      # 11 positive phrases with domain tags
│   ├── negative_phrases.vi.json  # 3 known-bad sequences (overcorrection prevention)
│   └── domains/
│       └── product_instruction.vi.json
├── ngrams/                  # Generated n-gram store (from scripts/build_ngram_store.py)
│   └── ngram_store.vi.json  # Merged bigrams/trigrams/fourgrams + domain + negative
├── matchers/                # YAML matcher configurations
│   ├── url.yaml, email.yaml, phone.yaml
│   ├── number.yaml, unit.yaml, money.yaml, percent.yaml
│   ├── code.yaml, date.yaml
│   └── chemical.yaml

data/lexicon/                # Compiled runtime artifacts (generated)
    └── trusted_lexicon.db   # Official SQLite DB (from build_lexicon_db.py)
```

---

## Milestones

### ✅ M1 — Basic Normalization (complete)
- Unicode normalizer (NFC, control chars, whitespace)
- Case masker (UPPER/LOWER/TITLE/MIXED/UNKNOWN, Vietnamese Đ/đ)
- Tokenizer with roundtrip guarantee

### ✅ M2 — Lexicon Store (complete)
- Backend-agnostic `LexiconStore` ABC with typed interface
- `JsonLexiconStore` — in-memory store loaded from built-in JSON resources only
- `SqliteLexiconStore` — query-based store backed by stdlib `sqlite3`, loads pre-built DB
- `HybridLexiconStore` — explicit primary/fallback composition
- `load_default_lexicon(mode)` factory with `"json"`, `"sqlite"`, `"hybrid"` modes
- Lexicon build pipeline (syllable, word, phrase, confusion, abbreviation builders)
- CLI lexicon subcommands (info, lookup, candidates, validate) with `--lexicon-mode` flag

### ✅ M3 — Protected Token Detection (complete)
- Regex-based matchers (URL, email, phone, number, unit, money, percent, code, date)
- Lexicon-based matcher (chemical terms from dictionary)
- Conflict resolution (priority + longest-span + insertion-order)
- Mask/restore roundtrip with placeholder tracking
- YAML-configurable matcher registry

### 📋 M4–M8
See [PROJECT.md](PROJECT.md) for the full plan.

---

## Configuration

Scoring and decision thresholds are defined in `src/vn_corrector/common/constants.py`:

```python
REPLACE_THRESHOLD = 0.85        # Minimum confidence to apply correction
MIN_MARGIN = 0.20               # Required margin over second-best candidate
AMBIGUOUS_MARGIN = 0.10         # Below this → flag as ambiguous
MAX_CANDIDATES_PER_TOKEN = 8
MAX_TOKENS_PER_WINDOW = 7
MAX_COMBINATIONS_PER_WINDOW = 5000
```

All thresholds are configurable. File-based YAML/JSON configuration is planned.

Protected token matchers are configured via YAML files in `resources/matchers/`:

```yaml
# Example: resources/matchers/number.yaml
name: number
priority: 10
span_type: number
patterns:
  - '\b\d+(?:[.,]\d+)+\b'
  - '\b\d+\b'
```

---

## Testing

```bash
# Run all tests (949+ tests across 24 files)
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_normalizer.py
pytest tests/test_protected_tokens.py

# Run Stage 4 tests
pytest tests/stage4_candidates/
```

---

## Code Quality

All code MUST follow these rules:

- **Use abstract base classes (ABC), not `Protocol`** — shared interfaces use `ABC` with `@abstractmethod`
- **No `Any` or `object` as type annotations** — use concrete types, generic types, or union types
- **No `# type: ignore` or `# noqa` suppression comments**
- **DRY — single source of truth** in `src/vn_corrector/common/` and `stage1_normalize/char_normalizer.py`

```bash
# Lint and format
ruff check src tests
ruff format --check src tests

# Type check
mypy src tests

# Test with coverage
pytest --cov=vn_corrector --cov-report=term-missing

# Pre-commit (all checks)
pre-commit run --all-files
```

Auto-format:

```bash
ruff format src tests
ruff check --fix src tests
```

---

## Roadmap

### Milestone 1 — Basic Normalization ✅

- [x] Unicode normalizer
- [x] Case masker
- [x] Tokenizer with roundtrip guarantee
- [x] CLI entrypoint

### Milestone 2 — Lexicon Store ✅

- [x] Backend-agnostic LexiconStore ABC with typed interface
- [x] JsonLexiconStore — in-memory store loaded from built-in JSON resources only
- [x] SqliteLexiconStore — query-based store backed by stdlib sqlite3, loads pre-built DB
- [x] HybridLexiconStore — explicit primary/fallback composition
- [x] `load_default_lexicon(mode)` factory with json/sqlite/hybrid modes
- [x] Syllable, word, unit, phrase, abbreviation, OCR confusion, and foreign-word indices
- [x] Lexicon build pipeline with validation and metadata
- [x] build_trusted_lexicon.py (generates JSONL) + build_lexicon_db.py (compiles SQLite DB)
- [x] CLI lexicon subcommands (info, lookup, candidates, validate) with --lexicon-mode flag

### Milestone 3 — Protected Tokens ✅

- [x] Regex-based protected token detector (URL, email, phone, number, unit, money, percent, code, date)
- [x] Domain lexicon protected matcher (chemical terms)
- [x] Priority-based conflict resolution
- [x] Mask/restore roundtrip with placeholder tracking
- [x] YAML-configurable matcher registry

### Milestone 4 — Candidate Generation ✅

- [x] `LexiconStoreInterface` ABC shared between stage2 and stage4
- [x] 8 source generators: original, syllable map, OCR confusion, word lexicon, abbreviation, phrase evidence, edit distance, domain-specific
- [x] Deterministic ranking with prior-score weighting
- [x] Token-level LRU cache with config-fingerprint invalidation
- [x] Candidate deduplication and evidence merging
- [x] Limit enforcement (per-token max, window combination cap)
- [x] Protected token bypass
- [x] Diagnostics / explainability helpers
- [x] Real-lexicon acceptance tests + golden YAML regression (20+11 cases)
- [x] Benchmark script (`scripts/bench_stage4_candidates.py`)
- [x] Debug CLI (`corrector candidates "text"`)
- [x] Strong typing: ABC interfaces, no `Protocol`, no `Any`, no `object`

### Milestone 5 — N-Gram Phrase Scorer ✅
- [x] `scripts/build_ngram_store.py` — generates merged n-gram store
- [x] Deterministic scoring with `PhraseScorer` (word validity, syllable freq, phrase n-gram, domain context, OCR confusion, edit distance, overcorrection penalty, negative phrase penalty)
- [x] Bounded windowing around ambiguous tokens with overlap merging
- [x] Combinatorial sequence generation with identity-path preservation and max-combination limits
- [x] Per-token `CorrectionEvidence` with score deltas and `format_explanation()` output
- [x] `format_scored_window()` diagnostics for debug CLI
- [x] Acceptance tests (6 cases) using live phrase data
- [x] 949+ tests across 24 files

### Milestone 6 — Decision Engine

- [ ] Confidence and margin calculation
- [ ] Replace / keep / flag decisions
- [ ] Explanation objects

### Milestone 7 — Evaluation Harness

- [ ] Gold test set format (JSONL)
- [ ] CER / WER / precision / recall / overcorrection rate

### Milestone 8 — Feedback Loop

- [ ] Correction logging format
- [ ] Human accepted/rejected labels
- [ ] Confusion map update script

---

## Versioning

This project follows semantic versioning (`MAJOR.MINOR.PATCH`). Current: `0.1.0` — early development.

---

## Contributing

Before opening a pull request:

1. Add or update tests for any behavior changes.
2. Run the full test suite and linter:

```bash
pytest
pylint src tests
```

3. Check [PROJECT.md](PROJECT.md) for architecture and design guidelines.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## Disclaimer

This project is under active development. Behavior may change before a stable `v1.0.0` release. The engine is designed to be **conservative by default** — it will not correct low-confidence spans silently.
