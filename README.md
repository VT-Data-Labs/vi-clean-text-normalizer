# vi-clean-text-normalizer

> Vietnamese OCR post-correction engine — conservative, explainable, and safe.

[![Python versions](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![CI](https://github.com/VT-Labs/vi-clean-text-normalizer/actions/workflows/ci.yml/badge.svg)](https://github.com/VT-Labs/vi-clean-text-normalizer/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-pytest-blue.svg)](#testing)
[![Lint](https://img.shields.io/badge/lint-ruff-purple.svg)](#code-quality)
[![Type Checked](https://img.shields.io/badge/type--checked-mypy-blue.svg)](#code-quality)
[![License](https://img.shields.io/github/license/VT-Labs/vi-clean-text-normalizer.svg)](LICENSE)
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

> **Status:** Alpha — Milestone 1 (Basic Normalization) completed.

### Implemented

- [x] Unicode normalization (NFC, invisible character removal, whitespace normalization)
- [x] Case masking and restoration (UPPER / LOWER / TITLE / MIXED)
- [x] Tokenization with roundtrip reconstruction guarantee
- [x] CLI entrypoint (Stage 0 normalization)
- [x] Shared types, constants, validation, and error enums
- [x] CI pipeline (pytest + pylint)

### In Progress

- [ ] Full correction pipeline (Stages 3–9)
- [ ] Protected token detection
- [ ] Lexicon builders and store
- [ ] Candidate generation and scoring
- [ ] Decision engine
- [ ] Evaluation harness
- [ ] PyPI release

### Known Limitations

- APIs may change before `v1.0.0`.
- Correction logic beyond basic normalization is not yet wired.
- See [PROJECT.md](PROJECT.md) for the full roadmap.

---

## Features

- **Unicode normalization** — NFC composition, invisible/control character removal, whitespace normalization (preserving intentional newlines)
- **Case masking** — detect case patterns (UPPER/LOWER/TITLE/MIXED), produce lowercase working copies, restore original casing after correction
- **Tokenization** — fine-grained token splitting with strict roundtrip guarantee: `reconstruct(tokenize(text)) == text`
- **Vietnamese detection** — correct identification of Vietnamese characters with tone marks across Unicode blocks
- **CLI interface** — single-text, batch file, interactive, and JSON output modes

---

## Installation

### From source

```bash
git clone https://github.com/dev-workstation/vi-clean-text-normalizer.git
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

---

## Architecture

The full pipeline (Stages 3–9 in development):

```text
OCR Raw Text
  ↓
Stage 0: Input Normalization
  ↓
Stage 1: Unicode Normalization       ← implemented
  ↓
Stage 2: Case Masking                ← implemented
  ↓
Stage 3: Protected Token Detection   ← not yet implemented
  ↓
Stage 4: Tokenization                ← implemented
  ↓
Stage 5: Candidate Generation        ← not yet implemented
  ↓
Stage 6: Candidate Scoring           ← not yet implemented
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
├── cli.py                  # CLI entrypoint
├── normalizer.py           # Unicode normalization (Stages 0-1)
├── case_mask.py            # Case detection and restoration (Stages 2, 8)
├── tokenizer.py            # Tokenization (Stage 4)
├── common/
│   ├── constants.py        # Thresholds, weights, pipeline constants
│   ├── errors.py           # Flag types, decision types, case patterns
│   ├── types.py            # Core dataclasses (Token, CaseMask, CorrectionResult, etc.)
│   └── validation.py       # Input validation helpers
├── lexicon/                # Lexicon store and builders (not yet populated)
└── utils/
    └── unicode.py          # Vietnamese character detection
```

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

---

## Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_normalizer.py
```

---

## Code Quality

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

### Milestone 2 — Lexicon Builder

- [ ] Syllable lexicon builder
- [ ] Word lexicon loader
- [ ] JSON/SQLite lexicon store

### Milestone 3 — Protected Tokens

- [ ] Regex-based protected token detector
- [ ] Domain lexicon protected matcher
- [ ] Unit/number/code detector

### Milestone 4 — Candidate Generation

- [ ] OCR confusion map loader
- [ ] Syllable map candidate generation
- [ ] Candidate source tracking

### Milestone 5 — N-Gram Phrase Scorer

- [ ] Bigram/trigram counter
- [ ] Phrase score lookup
- [ ] Window-based candidate scoring

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
