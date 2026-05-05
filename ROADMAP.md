# Milestone Roadmap — vi-clean-text-normalizer

Derived from [PROJECT.md](PROJECT.md) Sections 8 and 22.

---

## Phase 1 — Deterministic MVP (current)

| # | Milestone | Description | Dependencies |
|---|-----------|-------------|-------------|
| M1 | **Basic Normalization** | Unicode normalizer (NFC), case masker, basic tokenizer, reconstruction test | — |
| M2 | **Lexicon Builder** | Syllable lexicon builder, word lexicon loader, JSON/SQLite lexicon store | M1 |
| M3 | **Protected Token Detection** | Regex detector for numbers/units/URLs/emails, domain lexicon matcher, chemical/product code detector | M1 |
| M4 | **Candidate Generator** | Generation from original token, syllable map, confusion map; source tracking | M2, M3 |
| M5 | **N-Gram Phrase Scorer** | Bigram/trigram counter, phrase score lookup, window-based candidate scoring | M4 |
| M6 | **Decision Engine** | Confidence calculation, margin calculation, replace/keep/flag decisions, explanation object | M5 |
| M7 | **Evaluation Harness** | Gold test set (JSONL), CER/WER metrics, correction precision/recall, overcorrection rate | M6 |
| M8 | **Feedback Loop** | Correction log format, human accepted/rejected labels, confusion map update script, domain phrase update script | M7 |

### Milestone M1 — Basic Normalization

**Tasks:**
- [ ] `normalizer.py` — Unicode NFC normalization, control character removal, whitespace normalization
- [ ] `case_mask.py` — Case pattern detection (UPPER/LOWER/TITLE/MIXED/UNKNOWN), lowercase working copy, case restoration
- [ ] `tokenizer.py` — Token segmentation (VI_WORD, FOREIGN_WORD, NUMBER, UNIT, PUNCT, SPACE, NEWLINE), whitespace-preserving reconstruction
- [ ] Tests for all three modules

**Acceptance:** Input can be normalized and reconstructed without losing text. Uppercase/lowercase masks work.

### Milestone M2 — Lexicon Builder

**Tasks:**
- [ ] `lexicon/syllables.py` — Build `base → accented forms` from word list
- [ ] `lexicon/words.py` — Load/query known Vietnamese words
- [ ] `lexicon/store.py` — JSON-based lexicon store with query interface

**Acceptance:** Given a word list, system builds base → accented forms. Can query candidates by no-tone key.

### Milestone M3 — Protected Token Detection

**Tasks:**
- [ ] `protected_tokens.py` — Regex matchers for numbers, units, percentages, URLs, emails, phone numbers, dates, IDs
- [ ] Domain lexicon protected matcher for chemical/product terms
- [ ] Mixed-span splitting

**Acceptance:** `2'-FL`, `DHA`, `120ml`, URLs, numbers, and product codes are preserved.

### Milestone M4 — Candidate Generator

**Tasks:**
- [ ] `candidate_generator.py` — Generate candidates from original, syllable map, confusion map
- [ ] Candidate source tracking
- [ ] Limit enforcement (max_candidates_per_token=8)

**Acceptance:** `mùông` → generated candidates include `muỗng`. Protected tokens → single candidate (self).

### Milestone M5 — N-Gram Phrase Scorer

**Tasks:**
- [ ] `scorer.py` — Scoring formula implementation
- [ ] Bigram/trigram phrase score lookup
- [ ] Domain context scoring
- [ ] Window-based candidate scoring

**Acceptance:** `số mùông gạt ngang` corrects to `số muỗng gạt ngang`.

### Milestone M6 — Decision Engine

**Tasks:**
- [ ] `decision.py` — Decision logic (replace_threshold=0.85, min_margin=0.20)
- [ ] Flag generation for ambiguous/low-confidence spans
- [ ] Explanation object per decision

**Acceptance:** High-confidence examples corrected. Ambiguous examples flagged. Valid originals not overcorrected.

### Milestone M7 — Evaluation Harness

**Tasks:**
- [ ] `scripts/evaluate.py` — Load gold JSONL, compute CER/WER, precision/recall, overcorrection rate
- [ ] Gold test set in `data/evaluation/`

**Acceptance:** Running `scripts/evaluate.py` outputs metrics. Regression tests catch bad corrections.

### Milestone M8 — Feedback Loop

**Tasks:**
- [ ] Correction log format (JSON with timestamps, domain, changes, accepted/rejected)
- [ ] Confusion map update from feedback
- [ ] Domain phrase update from feedback
- [ ] Threshold tuning script

**Acceptance:** Human feedback can improve future correction.

---

## Phase 2 — Domain Adaptation

- Product label corpus collection
- Domain phrase mining from corpus
- Human feedback loop (UI or CLI)
- Better confidence tuning per domain

## Phase 3 — Model Reranker

- Small candidate reranker (ByT5 / ViT5 / BARTpho)
- Character/byte-level model integration
- Confidence calibration

## Phase 4 — OCR Feedback Integration

- Use OCR bounding boxes per span
- Use OCR confidence per span
- Image crop retry for low-confidence tokens
- Combine visual confidence with text correction confidence

## Phase 5 — Full Document Pipeline

- Layout-aware correction
- Table-aware correction
- Markdown/HTML-preserving correction
- Human review UI

---

## Success Criteria (per Section 9)

| Metric | Target |
|--------|--------|
| Correction precision | ≥ 0.95 |
| Protected-token violation rate | 0.0 |
| Overcorrection rate | ≤ 0.01 |

Recall can be improved later.
