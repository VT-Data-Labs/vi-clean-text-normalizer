# vi-clean-text-normalizer

> Vietnamese OCR post-correction engine — conservative, explainable, and safe.

[![Python versions](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![CI](https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer/actions/workflows/ci.yml/badge.svg)](https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/Vi-Lang-Foundation/vi-clean-text-normalizer.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

---

## Overview

`vi-clean-text-normalizer` repairs common Vietnamese OCR errors — tone-marking mistakes, uppercase diacritic errors, and character confusions — while preserving layout-sensitive tokens, foreign terms, product codes, numbers, units, and domain-specific vocabulary.

**Conservative by default** — when uncertain, it keeps the original text and flags the ambiguity rather than guessing.

Primary use cases:
- Vietnamese OCR post-processing
- Vietnamese diacritic restoration
- Product label / instruction text correction
- Mixed Vietnamese + English + chemical + numeric text correction

---

## Quick Start

```bash
pip install vi-clean-text-normalizer
```

```python
from vn_corrector import correct_text

result = correct_text("neu do am vua du")
print(result.corrected_text)   # "nếu độ ấm vừa đủ"
print(result.confidence)       # 0.84
print(result.changes)          # [CorrectionChange(...), ...]
```

Or from the CLI:

```bash
corrector "neu do am vua du"
```

---

## Installation

```bash
pip install vi-clean-text-normalizer
```

### From source

```bash
git clone https://github.com/Vi-Lang-Foundation/vi-clean-text-normalizer.git
cd vi-clean-text-normalizer
uv sync
```

---

## CLI Usage

```bash
# Correct a single phrase
corrector "neu do am vua du"

# JSON output
corrector --json "SỐ MÙÔNG (GẠT NGANG)"

# Read from stdin
corrector < input.txt

# Interactive mode
corrector -i
```

### Lexicon inspection

```bash
corrector lexicon info
corrector lexicon lookup muỗng
corrector lexicon candidates muong
corrector lexicon validate
```

### Candidate debug view

```bash
corrector candidates "người đẫn đường"
```

---

## Python API

```python
# Full correction pipeline
from vn_corrector import correct_text

result = correct_text("neu do am vua du", domain="milk_instruction")
result.original_text    # "neu do am vua du"
result.corrected_text   # "nếu độ ấm vừa đủ"
result.confidence       # 0.84
result.changes          # applied corrections
result.flags            # warnings
```

For production (reuse loaded dependencies):

```python
from vn_corrector.pipeline import TextCorrector

corrector = TextCorrector()
for line in many_lines:
    result = corrector.correct(line)
```

### Individual components

```python
from vn_corrector.normalizer import normalize
from vn_corrector.tokenizer import tokenize, reconstruct
from vn_corrector.protected_tokens import protect
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for full API documentation and architecture details.

---

## Project Status

> **Status:** Milestone 7 complete — evaluating with CER/WER/precision/recall.

- [x] Unicode normalization & case masking
- [x] Tokenization with roundtrip guarantee
- [x] Protected token detection (URL, email, phone, codes, chemicals)
- [x] Pluggable lexicon store (JSON / SQLite / Hybrid)
- [x] Candidate generation (8 source generators)
- [x] N-gram phrase scoring with context-aware windowing
- [x] Decision engine with confidence thresholds and flags
- [x] Evaluation harness
- [x] **Full correction pipeline** (M6.5)

See [DEVELOPMENT.md](DEVELOPMENT.md) for the detailed milestone roadmap.

---

## Configuration

Thresholds in `src/vn_corrector/common/constants.py`:

| Constant | Default | Description |
|---|---|---|
| `REPLACE_THRESHOLD` | 0.85 | Min confidence to apply correction |
| `MIN_MARGIN` | 0.20 | Required margin over second-best |
| `AMBIGUOUS_MARGIN` | 0.10 | Below this → flag as ambiguous |

Pipeline configuration via `PipelineConfig`:

```python
from vn_corrector.pipeline import PipelineConfig

config = PipelineConfig(
    min_accept_confidence=0.90,
    max_candidates_per_token=6,
    fail_closed=True,
)
result = correct_text("neu do am", config=config)
```

---

## Contributing

1. Read [PROJECT.md](PROJECT.md) for design guidelines and architecture.
2. Read [DEVELOPMENT.md](DEVELOPMENT.md) for development workflow, code conventions, and testing.
3. Open a pull request with tests for any behavior changes.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

---

## Disclaimer

This project is under active development. The engine is designed to be **conservative by default** — it will not correct low-confidence spans silently. Behavior may change before `v1.0.0`.
