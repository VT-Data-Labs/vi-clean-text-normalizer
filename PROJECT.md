# PROJECT.md — Vietnamese Lexicon + OCR Correction System

## 1. Project Goal

Build a production-grade Vietnamese OCR post-correction engine that can repair common Vietnamese OCR errors while preserving the original meaning, layout-sensitive tokens, foreign terms, product codes, numbers, units, and domain-specific vocabulary.

The system should not behave like a free-form rewriting model. It should act as a conservative correction engine with confidence scoring, explainable changes, and safe fallback behavior.

Primary use cases:

- Vietnamese OCR post-processing
- Vietnamese diacritic restoration
- Uppercase Vietnamese correction
- Product label / instruction text correction
- Mixed Vietnamese + English + chemical + numeric text correction
- Domain-specific correction for noisy OCR output

Example target corrections:

```text
SỐ MÙÔNG (GẠT NGANG)
→ SỐ MUỖNG (GẠT NGANG)
```

```text
LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ
→ LÀM NGUỘI NHANH VÀ KIỂM TRA NHIỆT ĐỘ
```

```text
RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ THEO LƯỢNG HƯỚNG DẪN
→ RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ THEO LƯỢNG HƯỚNG DẪN
```

---

## 2. Non-Goals

This system is not intended to:

- Replace the OCR model
- Reconstruct broken page layout
- Guess missing text from severely damaged OCR
- Rewrite Vietnamese into more formal Vietnamese
- Translate English or foreign terms into Vietnamese
- Normalize all slang into formal language unless explicitly configured
- Correct legal, medical, or scientific terms without strong domain lexicon support
- Auto-correct low-confidence spans
- Hallucinate missing content

If the input is too degraded, ambiguous, or layout-corrupted, the system must flag the issue instead of forcing a correction.

---

## 3. Core Principle

The engine must be conservative.

Correction should happen only when:

1. The candidate is linguistically plausible.
2. The candidate fits the local context.
3. The candidate fits the domain context.
4. The confidence score is high enough.
5. The margin over the second-best candidate is large enough.
6. The span is not protected.
7. The correction does not destroy numbers, codes, units, or foreign terms.

Default behavior:

```text
When uncertain, keep original and flag ambiguity.
```

---

## 4. High-Level Architecture

```text
OCR Raw Text
  ↓
Stage 0: Input Normalization
  ↓
Stage 1: Unicode Normalization
  ↓
Stage 2: Case Masking
  ↓
Stage 3: Protected Token Detection
  ↓
Stage 4: Tokenization / Span Segmentation
  ↓
Stage 5: Candidate Generation
  ↓
Stage 6: Candidate Scoring
  ↓
Stage 7: Correction Decision
  ↓
Stage 8: Case Restoration
  ↓
Stage 9: Output + Change Log + Flags
```

---

## 5. Repository Structure

Recommended initial structure:

```text
vn-correction-engine/
├── PROJECT.md
├── README.md
├── pyproject.toml
├── src/
│   └── vn_corrector/
│       ├── __init__.py
│       ├── config.py
│       ├── pipeline.py
│       ├── normalizer.py
│       ├── case_mask.py
│       ├── tokenizer.py
│       ├── protected_tokens.py
│       ├── candidate_generator.py
│       ├── scorer.py
│       ├── decision.py
│       ├── output.py
│       ├── lexicon/
│       │   ├── __init__.py
│       │   ├── store.py
│       │   ├── builders.py
│       │   ├── syllables.py
│       │   ├── words.py
│       │   ├── phrases.py
│       │   └── confusions.py
│       └── utils/
│           ├── unicode.py
│           ├── edit_distance.py
│           └── text.py
├── data/
│   ├── raw/
│   ├── processed/
│   ├── lexicon/
│   ├── domain/
│   └── evaluation/
├── scripts/
│   ├── build_syllable_lexicon.py
│   ├── build_word_lexicon.py
│   ├── build_phrase_ngram.py
│   ├── build_confusion_map.py
│   ├── evaluate.py
│   └── demo.py
├── tests/
│   ├── test_unicode.py
│   ├── test_case_mask.py
│   ├── test_protected_tokens.py
│   ├── test_candidate_generation.py
│   ├── test_scorer.py
│   ├── test_decision.py
│   └── test_pipeline.py
└── examples/
    ├── milk_instruction_input.txt
    ├── milk_instruction_output.json
    └── mixed_language_input.txt
```

---

## 6. Data Assets

The system should use several lexicon layers instead of a single dictionary.

### 6.1 Vietnamese Syllable Lexicon

Purpose:

- Map no-tone syllables to valid Vietnamese accented forms.
- Support diacritic restoration.
- Support candidate generation.

Example:

```json
{
  "base": "muong",
  "forms": ["muông", "muống", "muồng", "muỗng", "mường", "mượng"]
}
```

Build method:

```text
Vietnamese word list
→ lowercase
→ split by whitespace
→ remove tone marks
→ group accented forms by no-tone base
```

Required fields:

```json
{
  "base": "muong",
  "forms": ["muỗng", "mường", "muồng"],
  "freq": {
    "muỗng": 0.91,
    "mường": 0.05,
    "muồng": 0.04
  }
}
```

### 6.2 Vietnamese Word Lexicon

Purpose:

- Validate known Vietnamese words.
- Rank candidates by commonness.
- Avoid replacing valid high-confidence words with rare words.

Example:

```json
{
  "surface": "hướng dẫn",
  "normalized": "huong dan",
  "type": "common_word",
  "freq": 0.95,
  "domain": null
}
```

### 6.3 Phrase / N-Gram Lexicon

Purpose:

- Resolve ambiguity using context.
- Repair semantic OCR mistakes such as `người` vs `nguội`.

Example:

```json
{
  "phrase": "làm nguội nhanh",
  "n": 3,
  "freq": 0.94,
  "domain": "product_instruction"
}
```

Important examples:

```text
số muỗng gạt ngang
rót nước vào dụng cụ pha chế
làm nguội nhanh
kiểm tra nhiệt độ
hướng dẫn sử dụng
```

### 6.4 Domain Lexicon

Purpose:

- Preserve domain-specific words.
- Prevent overcorrection of chemical/product/technical terms.

Example terms:

```text
Lactose
maltodextrin
alpha-lactalbumin
2'-Fucosyllactose
2'-FL
3'-SL
6'-SL
LNT
DHA
ARA
Bifidobacterium
oligosaccharid
```

Required schema:

```json
{
  "surface": "2'-Fucosyllactose",
  "normalized": "2'-fucosyllactose",
  "type": "chemical",
  "protected": true,
  "domain": "milk_formula"
}
```

### 6.5 OCR Confusion Map

Purpose:

- Generate candidates for common OCR mistakes.
- Capture model-specific error patterns.

Example:

```json
{
  "mùông": ["muỗng"],
  "đẫn": ["dẫn", "dần"],
  "dủ": ["đủ"],
  "lâm": ["làm"],
  "rốt": ["rót"],
  "người": ["nguội"]
}
```

Confusion map should be learned from real OCR logs over time.

---

## 7. Pipeline Stages

## Stage 0 — Input Normalization

Input may be:

- Plain text
- Markdown
- OCR HTML
- OCR block text
- One line
- Multi-line document

The system should preserve structure where possible.

Input example:

```text
RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ THEO LƯỢNG HƯỚNG DẪN.
```

Output:

```json
{
  "text": "RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ THEO LƯỢNG HƯỚNG DẪN.",
  "format": "plain_text"
}
```

Acceptance criteria:

- Input text is not modified semantically.
- Newlines are preserved.
- Markdown/HTML tokens are either preserved or protected.

---

## Stage 1 — Unicode Normalization

Responsibilities:

- Normalize Unicode to NFC.
- Remove invisible control characters.
- Normalize weird spaces.
- Preserve Vietnamese characters.
- Preserve punctuation unless explicitly configured.

Do:

```text
NFD/NFKD weird text → NFC canonical Vietnamese text
```

Do not:

```text
Remove all punctuation
Lowercase blindly
Delete symbols inside chemical names
```

Acceptance criteria:

- `đ`, `Đ`, tone marks, and Vietnamese vowels are preserved.
- Combining marks are normalized.
- No accidental ASCII-only conversion.

---

## Stage 2 — Case Masking

Purpose:

- Avoid correcting Vietnamese uppercase directly.
- Many OCR/VLM systems produce worse Vietnamese tone marks in uppercase.
- Work internally in lowercase, then restore original casing.

Example:

```text
Input:  RỐT NƯỚC VÀO DỤNG CỤ
Work:   rốt nước vào dụng cụ
Output: RÓT NƯỚC VÀO DỤNG CỤ
```

Implementation idea:

```json
{
  "original": "RỐT",
  "working": "rốt",
  "case_pattern": "UPPER"
}
```

Case patterns:

```text
LOWER
UPPER
TITLE
MIXED
UNKNOWN
```

Acceptance criteria:

- Uppercase input returns uppercase output.
- Title-case input returns title-case output.
- Mixed-case product codes are protected and not case-normalized.

---

## Stage 3 — Protected Token Detection

Protected tokens must not be modified.

Protect:

- Numbers
- Units
- Percentages
- Product codes
- Chemical terms
- Brand names
- Foreign words
- URLs
- Emails
- Phone numbers
- Dates
- IDs
- HTML tags
- Markdown links
- Table delimiters

Examples:

```text
2'-FL
3'-SL
120ml
0-2 tháng
DHA
ARA
LNT
alpha-lactalbumin
```

Output example:

```json
{
  "text": "Lactose, DHA, SỐ MÙÔNG",
  "spans": [
    {"text": "Lactose", "type": "foreign_or_chemical", "protected": true},
    {"text": "DHA", "type": "abbreviation", "protected": true},
    {"text": "SỐ", "type": "vietnamese", "protected": false},
    {"text": "MÙÔNG", "type": "vietnamese", "protected": false}
  ]
}
```

Acceptance criteria:

- Protected tokens are byte-for-byte preserved unless configured otherwise.
- Vietnamese correction only applies to Vietnamese spans.
- Mixed spans are split safely.

---

## Stage 4 — Tokenization / Span Segmentation

Purpose:

- Split text into correction units.
- Preserve punctuation and whitespace.
- Allow phrase scoring over Vietnamese tokens.

Token types:

```text
VI_WORD
FOREIGN_WORD
NUMBER
UNIT
PUNCT
SPACE
NEWLINE
PROTECTED
UNKNOWN
```

Example:

```text
SỐ MÙÔNG (GẠT NGANG)
```

Tokens:

```json
[
  {"text": "SỐ", "type": "VI_WORD"},
  {"text": " ", "type": "SPACE"},
  {"text": "MÙÔNG", "type": "VI_WORD"},
  {"text": " ", "type": "SPACE"},
  {"text": "(", "type": "PUNCT"},
  {"text": "GẠT", "type": "VI_WORD"},
  {"text": " ", "type": "SPACE"},
  {"text": "NGANG", "type": "VI_WORD"},
  {"text": ")", "type": "PUNCT"}
]
```

Acceptance criteria:

- Whitespace can be reconstructed exactly.
- Punctuation is not lost.
- Correction operates on word tokens but reconstructs full text.

---

## Stage 5 — Candidate Generation

Generate possible corrections for each Vietnamese token or short phrase.

Candidate sources:

1. Exact token
2. OCR confusion map
3. No-tone Vietnamese syllable map
4. Edit-distance neighbors
5. Phrase-specific corrections
6. Domain-specific corrections

Example:

```text
mùông
```

Candidates:

```json
[
  {"text": "mùông", "source": "original"},
  {"text": "muỗng", "source": "ocr_confusion"},
  {"text": "mường", "source": "syllable_map"},
  {"text": "muông", "source": "syllable_map"}
]
```

Constraints:

- Limit max candidates per token.
- Do not generate candidates for protected tokens.
- Prefer candidate generation for suspicious tokens.
- Avoid combinatorial explosion.

Suggested limits:

```text
max_candidates_per_token = 8
max_tokens_per_window = 7
max_combinations_per_window = 5000
```

Acceptance criteria:

- Original token is always included.
- Protected tokens have only one candidate: themselves.
- Candidate source is recorded.

---

## Stage 6 — Candidate Scoring

Score candidates using multiple signals.

Suggested scoring formula:

```text
score =
  word_validity_score
+ syllable_frequency_score
+ phrase_ngram_score
+ domain_context_score
+ ocr_confusion_score
+ edit_distance_score
- overcorrection_penalty
- protected_token_penalty
- rare_word_penalty
```

### 6.1 Word Validity Score

Reward known Vietnamese words.

```text
known common word → positive
unknown word → neutral or negative
```

### 6.2 Syllable Frequency Score

Reward common accented form for no-tone base.

Example:

```text
muong → muỗng > mường > muồng
```

### 6.3 Phrase N-Gram Score

Reward locally plausible phrase.

Example:

```text
số muỗng gạt ngang
```

should score higher than:

```text
số mường gạt ngang
```

### 6.4 Domain Context Score

Reward candidates appearing in domain lexicon.

Example domain: milk instruction.

```text
làm nguội nhanh
số muỗng gạt ngang
pha chế theo lượng hướng dẫn
```

### 6.5 OCR Confusion Score

Reward known OCR mistake corrections.

Example:

```text
mùông → muỗng
rốt → rót
lâm → làm
```

### 6.6 Overcorrection Penalty

Penalize unnecessary changes.

Do not change valid input unless there is strong evidence.

Example:

```text
người dẫn chương trình
```

must not become:

```text
nguội dần chương trình
```

Acceptance criteria:

- Score explanation is available for every applied correction.
- Original text can win if confidence is low.
- Rare but protected domain terms are not penalized incorrectly.

---

## Stage 7 — Correction Decision

The engine should compare the best candidate with the original and second-best candidate.

Required decision fields:

```json
{
  "original": "mùông",
  "best": "muỗng",
  "best_score": 0.93,
  "second_best": "mường",
  "second_score": 0.41,
  "margin": 0.52,
  "decision": "replace"
}
```

Decision types:

```text
KEEP_ORIGINAL
REPLACE
FLAG_AMBIGUOUS
FLAG_UNKNOWN
PROTECTED
```

Suggested thresholds:

```text
replace_threshold = 0.85
min_margin = 0.20
ambiguous_margin = 0.10
```

Rules:

```text
If protected → keep original.
If best_score >= replace_threshold and margin >= min_margin → replace.
If best_score is close to second_best → flag ambiguous.
If all candidates are weak → keep original and flag unknown.
```

Acceptance criteria:

- Low-confidence text is not silently changed.
- Ambiguous spans are flagged.
- Decisions are explainable.

---

## Stage 8 — Case Restoration

Restore case after correction.

Examples:

```text
rót → RÓT
muỗng → MUỖNG
làm nguội → LÀM NGUỘI
```

Rules:

```text
Original UPPER → corrected UPPER
Original LOWER → corrected LOWER
Original TITLE → corrected TITLE
Original MIXED → preserve original unless safe
Protected token → preserve byte-for-byte
```

Acceptance criteria:

- Uppercase Vietnamese output has correct uppercase tone marks.
- Chemical/product codes keep original casing.
- Mixed-case tokens are not destroyed.

---

## Stage 9 — Output Format

The engine must return both corrected text and structured metadata.

Example:

```json
{
  "original_text": "SỐ MÙÔNG (GẠT NGANG)",
  "corrected_text": "SỐ MUỖNG (GẠT NGANG)",
  "confidence": 0.93,
  "changes": [
    {
      "span": "MÙÔNG",
      "replacement": "MUỖNG",
      "start": 3,
      "end": 8,
      "confidence": 0.93,
      "reason": "domain phrase match: số muỗng gạt ngang",
      "candidate_source": ["ocr_confusion", "phrase_ngram"]
    }
  ],
  "flags": []
}
```

Ambiguous example:

```json
{
  "original_text": "NGƯỜI ĐẪN",
  "corrected_text": "NGƯỜI ĐẪN",
  "confidence": 0.48,
  "changes": [],
  "flags": [
    {
      "span": "ĐẪN",
      "type": "AMBIGUOUS",
      "candidates": ["DẪN", "DẦN"],
      "reason": "insufficient context"
    }
  ]
}
```

Acceptance criteria:

- Every correction is traceable.
- Every flag is actionable.
- Output can be used for human review and future training.

---

## 8. MVP Implementation Plan

## Milestone 1 — Basic Normalization

Build:

- Unicode normalizer
- Case masker
- Basic tokenizer
- Reconstruction test

Done when:

- Input can be normalized and reconstructed without losing text.
- Uppercase/lowercase masks work.
- Tests pass for Vietnamese characters.

## Milestone 2 — Lexicon Builder

Build:

- Syllable lexicon builder
- Word lexicon loader
- Simple JSON/SQLite lexicon store

Done when:

- Given a word list, system builds `base → accented forms`.
- Can query candidates by no-tone key.

## Milestone 3 — Protected Tokens

Build:

- Regex-based protected token detector
- Domain lexicon protected matcher
- Unit/number/code detector

Done when:

- `2'-FL`, `DHA`, `120ml`, URLs, numbers, and product codes are preserved.

## Milestone 4 — Candidate Generator

Build:

- Candidate generation from original token
- Candidate generation from syllable map
- Candidate generation from confusion map
- Candidate source tracking

Done when:

- `mùông` generates `muỗng`.
- `đẫn` generates `dẫn`, `dần`.
- Protected tokens do not generate alternatives.

## Milestone 5 — N-Gram Phrase Scorer

Build:

- Bigram/trigram counter
- Phrase score lookup
- Window-based candidate scoring

Done when:

- `số mùông gạt ngang` corrects to `số muỗng gạt ngang`.
- `lâm người nhanh` corrects to `làm nguội nhanh` only when domain phrase exists.

## Milestone 6 — Decision Engine

Build:

- Confidence calculation
- Margin calculation
- Replace/keep/flag decisions
- Explanation object

Done when:

- High-confidence examples are corrected.
- Ambiguous examples are flagged.
- Valid original phrases are not overcorrected.

## Milestone 7 — Evaluation Harness

Build:

- Gold test set format
- Character error rate
- Word error rate
- Correction precision
- Correction recall
- Overcorrection rate

Done when:

- Running `scripts/evaluate.py` outputs metrics.
- Regression tests catch bad correction changes.

## Milestone 8 — Feedback Loop

Build:

- Correction log format
- Human accepted/rejected labels
- Confusion map update script
- Domain phrase update script

Done when:

- Human feedback can improve future correction.

---

## 9. Evaluation Metrics

Measure not only accuracy, but also safety.

Required metrics:

```text
CER before correction
CER after correction
WER before correction
WER after correction
correction precision
correction recall
overcorrection rate
protected-token violation rate
ambiguous-flag rate
```

Important definitions:

### Correction Precision

```text
Of all applied corrections, how many were correct?
```

This is the most important metric for production.

### Correction Recall

```text
Of all real OCR errors, how many did we fix?
```

Useful, but less important than precision.

### Overcorrection Rate

```text
How often did we change correct text into wrong text?
```

This must be very low.

Target initial production thresholds:

```text
correction_precision >= 0.95
protected_token_violation_rate = 0
overcorrection_rate <= 0.01
```

Recall can be improved later.

---

## 10. Gold Dataset Format

Use JSONL.

Each line:

```json
{
  "id": "milk_0001",
  "domain": "milk_instruction",
  "ocr_text": "SỐ MÙÔNG (GẠT NGANG)",
  "gold_text": "SỐ MUỖNG (GẠT NGANG)",
  "protected_spans": [],
  "notes": "uppercase Vietnamese OCR tone/shape error"
}
```

Ambiguous case:

```json
{
  "id": "ambiguous_0001",
  "domain": "general",
  "ocr_text": "NGƯỜI ĐẪN",
  "gold_text": null,
  "expected_decision": "FLAG_AMBIGUOUS",
  "notes": "not enough context"
}
```

Protected token case:

```json
{
  "id": "chem_0001",
  "domain": "milk_formula",
  "ocr_text": "2'-FL, DHA, ARA, LNT",
  "gold_text": "2'-FL, DHA, ARA, LNT",
  "protected_spans": ["2'-FL", "DHA", "ARA", "LNT"]
}
```

---

## 11. Configuration

Example config:

```yaml
correction:
  replace_threshold: 0.85
  min_margin: 0.20
  max_candidates_per_token: 8
  max_tokens_per_window: 7
  max_combinations_per_window: 5000

normalization:
  unicode_form: NFC
  preserve_markdown: true
  preserve_html: true

case:
  use_case_mask: true
  restore_case: true

protected_tokens:
  protect_numbers: true
  protect_units: true
  protect_urls: true
  protect_emails: true
  protect_chemical_terms: true
  protect_product_codes: true

scoring:
  word_validity_weight: 1.0
  syllable_frequency_weight: 0.8
  phrase_ngram_weight: 2.5
  domain_context_weight: 3.0
  ocr_confusion_weight: 1.5
  edit_distance_weight: 0.5
  overcorrection_penalty: 2.0
```

---

## 12. Minimal Python Interfaces

### Pipeline API

```python
from vn_corrector.pipeline import VietnameseCorrectionPipeline

pipeline = VietnameseCorrectionPipeline.from_config("config.yaml")

result = pipeline.correct(
    "SỐ MÙÔNG (GẠT NGANG)",
    domain="milk_instruction",
)

print(result.corrected_text)
print(result.changes)
print(result.flags)
```

### Result Object

```python
@dataclass
class CorrectionResult:
    original_text: str
    corrected_text: str
    confidence: float
    changes: list[CorrectionChange]
    flags: list[CorrectionFlag]
```

### Change Object

```python
@dataclass
class CorrectionChange:
    original: str
    replacement: str
    start: int
    end: int
    confidence: float
    reason: str
    candidate_sources: list[str]
```

### Flag Object

```python
@dataclass
class CorrectionFlag:
    span: str
    start: int
    end: int
    type: str
    candidates: list[str]
    reason: str
```

---

## 13. Initial Test Cases

### Must Correct

```text
SỐ MÙÔNG (GẠT NGANG)
→ SỐ MUỖNG (GẠT NGANG)
```

```text
RỐT NƯỚC VÀO DỤNG CỤ PHA CHẾ
→ RÓT NƯỚC VÀO DỤNG CỤ PHA CHẾ
```

```text
LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ
→ LÀM NGUỘI NHANH VÀ KIỂM TRA NHIỆT ĐỘ
```

```text
NẾU ĐỘ ẤM VỪA DỦ
→ NẾU ĐỘ ẤM VỪA ĐỦ
```

### Must Not Change

```text
NGƯỜI DẪN CHƯƠNG TRÌNH
→ NGƯỜI DẪN CHƯƠNG TRÌNH
```

```text
2'-FL, DHA, ARA, LNT
→ 2'-FL, DHA, ARA, LNT
```

```text
120ml nước ở nhiệt độ 40°C
→ 120ml nước ở nhiệt độ 40°C
```

### Must Flag Ambiguous

```text
NGƯỜI ĐẪN
→ FLAG_AMBIGUOUS
```

```text
DAN
→ FLAG_AMBIGUOUS
```

---

## 14. Error Classes

Use explicit error/flag classes.

```text
AMBIGUOUS_DIACRITIC
UNKNOWN_TOKEN
LOW_CONFIDENCE
PROTECTED_TOKEN
MIXED_LANGUAGE_SPAN
POSSIBLE_LAYOUT_ERROR
POSSIBLE_OCR_DESTRUCTION
DOMAIN_TERM_UNKNOWN
```

Example:

```json
{
  "type": "POSSIBLE_OCR_DESTRUCTION",
  "span": "MLI0N6",
  "reason": "token too far from known Vietnamese candidates"
}
```

---

## 15. Logging and Feedback

Every correction should be logged.

Log format:

```json
{
  "timestamp": "2026-05-05T00:00:00Z",
  "domain": "milk_instruction",
  "original_text": "SỐ MÙÔNG",
  "corrected_text": "SỐ MUỖNG",
  "changes": [
    {
      "from": "MÙÔNG",
      "to": "MUỖNG",
      "confidence": 0.93,
      "accepted": null
    }
  ]
}
```

Human feedback:

```json
{
  "from": "MÙÔNG",
  "to": "MUỖNG",
  "accepted": true
}
```

Rejected correction:

```json
{
  "from": "NGƯỜI DẪN",
  "to": "NGUỘI DẦN",
  "accepted": false,
  "reason": "context was TV presenter, not product instruction"
}
```

Use logs to update:

- Confusion map
- Domain phrases
- Candidate weights
- Thresholds
- Gold test cases

---

## 16. Model Integration: Optional Later Stage

Do not start with fine-tuning.

Add a model only after deterministic pipeline and logs exist.

Recommended model roles:

### Good Use

```text
Candidate reranking
Confidence estimation
Ambiguity classification
Span-level correction suggestion
```

### Bad Use

```text
Raw OCR → LLM → rewritten text
```

Preferred model types:

```text
ByT5-style byte/character model
ViT5 correction model
BARTpho-style Vietnamese seq2seq
Small transformer reranker
```

Model input example:

```json
{
  "context": "số mùông gạt ngang",
  "candidates": [
    "số muỗng gạt ngang",
    "số mường gạt ngang",
    "số muông gạt ngang"
  ]
}
```

Model output:

```json
{
  "best_index": 0,
  "confidence": 0.94
}
```

The model should not be allowed to invent arbitrary text in production mode.

---

## 17. Safety Rules

1. Never modify protected tokens.
2. Never apply low-confidence correction silently.
3. Never rewrite meaning unless configured for semantic normalization.
4. Never assume all text is Vietnamese.
5. Never rely on dictionary alone.
6. Never rely on model alone.
7. Always return original text if no safe correction exists.
8. Always log applied changes.
9. Always expose confidence.
10. Always make regression tests from real failures.

---

## 18. Development Rules for Code Agents

When editing this project, follow these rules:

1. Keep modules small and testable.
2. Do not put all logic in `pipeline.py`.
3. Add unit tests for every correction rule.
4. Add regression tests for every bug fix.
5. Preserve original text offsets when possible.
6. Do not introduce free-form LLM rewriting into the core pipeline.
7. Do not auto-correct protected tokens.
8. Prefer explicit scoring and explanation over hidden magic.
9. Any new correction rule must include examples.
10. Any new threshold must be configurable.

---

## 19. First MVP Build Checklist

Implement in this order:

```text
[ ] Unicode normalizer
[ ] Case masker
[ ] Tokenizer
[ ] Protected token detector
[ ] Syllable lexicon builder
[ ] Confusion map loader
[ ] Candidate generator
[ ] Bigram/trigram phrase scorer
[ ] Decision engine
[ ] Output formatter
[ ] Evaluation script
[ ] Feedback log format
```

Do not implement model fine-tuning before these are done.

---

## 20. Example End-to-End Behavior

Input:

```text
LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ. NẾU ĐỘ ẤM VỪA DỦ, CHO TRẺ DÙNG NGAY.
```

Output:

```json
{
  "original_text": "LÂM NGƯỜI NHANH VÀ KIỂM TRA NHIỆT ĐỘ. NẾU ĐỘ ẤM VỪA DỦ, CHO TRẺ DÙNG NGAY.",
  "corrected_text": "LÀM NGUỘI NHANH VÀ KIỂM TRA NHIỆT ĐỘ. NẾU ĐỘ ẤM VỪA ĐỦ, CHO TRẺ DÙNG NGAY.",
  "confidence": 0.91,
  "changes": [
    {
      "span": "LÂM NGƯỜI",
      "replacement": "LÀM NGUỘI",
      "confidence": 0.92,
      "reason": "domain phrase match: làm nguội nhanh"
    },
    {
      "span": "DỦ",
      "replacement": "ĐỦ",
      "confidence": 0.95,
      "reason": "OCR confusion map + phrase context: vừa đủ"
    }
  ],
  "flags": []
}
```

---

## 21. Production Boundary

The system works best for:

```text
tone mark errors
uppercase Vietnamese OCR errors
minor OCR character confusions
common phrase-level OCR mistakes
domain-specific repeated wording
```

The system works poorly for:

```text
severely destroyed characters
missing words
broken reading order
rare proper nouns
foreign/code-heavy text without protection
low-context fragments
out-of-domain vocabulary
```

When the system cannot safely correct, it must return:

```text
original text + flags
```

not a guessed correction.

---

## 22. Long-Term Roadmap

### Phase 1 — Deterministic MVP

- Lexicon
- N-gram scorer
- Confusion map
- Protected tokens
- Conservative correction

### Phase 2 — Domain Adaptation

- Product label corpus
- Domain phrase mining
- Human feedback loop
- Better confidence tuning

### Phase 3 — Model Reranker

- Small candidate reranker
- Character/byte-level model
- Confidence calibration

### Phase 4 — OCR Feedback Integration

- Use OCR bounding boxes
- Use OCR confidence per span
- Use image crop retry for low-confidence tokens
- Combine visual confidence with text correction confidence

### Phase 5 — Full Document Pipeline

- Layout-aware correction
- Table-aware correction
- Markdown/HTML-preserving correction
- Human review UI

---

## 23. Final Rule

The goal is not to correct everything.

The goal is to correct only what is safe, explainable, and measurable.

A production Vietnamese OCR correction system should prefer:

```text
high precision + useful flags
```

over:

```text
high recall + hallucinated corrections
```


