# vi-clean-text-normalizer

Vietnamese OCR post-correction engine — conservative, explainable, and safe.

## Overview

A production-grade pipeline for repairing common Vietnamese OCR errors while preserving original meaning, layout-sensitive tokens, foreign terms, product codes, numbers, units, and domain-specific vocabulary.

## Project Status

Initial scaffold — no features implemented yet.

## Architecture

```text
OCR Raw Text
  ↓
Stage 0: Input Normalization
Stage 1: Unicode Normalization
Stage 2: Case Masking
Stage 3: Protected Token Detection
Stage 4: Tokenization / Span Segmentation
Stage 5: Candidate Generation
Stage 6: Candidate Scoring
Stage 7: Correction Decision
Stage 8: Case Restoration
Stage 9: Output + Change Log + Flags
```

## Getting Started

```bash
# Create a virtual environment
uv venv

# Install the package in editable mode
uv pip install -e .

# Run tests
pytest
```

## Project Structure

```
├── src/vn_corrector/       # Core package
│   ├── lexicon/            # Lexicon store, builders, syllable/word/phrase data
│   └── utils/              # Unicode, edit distance, text helpers
├── tests/                  # Test suite
├── data/                   # Lexicon, domain, evaluation datasets
├── scripts/                # Build, evaluation, and demo scripts
└── examples/               # Sample inputs and outputs
```

See [PROJECT.md](PROJECT.md) for the full specification.

## License

MIT
