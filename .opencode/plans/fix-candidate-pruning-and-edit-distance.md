# Fix: Candidate pruning and edit-distance scoring for accentless recovery

## Summary

Three-regression fix for `accentless_004` (`neu do am vua du` → `nếu độ ấm vừa đủ`):

1. **#1 — Search-space bug**: candidate pruning drops best alternatives because it truncates by list order, not score.
2. **#3 — Scoring bug**: `edit_distance` is `None` for syllable_map/domain_specific candidates, so the scorer gives changed tokens zero edit-distance credit — the identity sequence crushes all corrections.
3. **#2 — Data gap** (future): n-gram store lacks this phrase. Not fixed here; n-grams should improve confidence, not be required for obvious accent restoration.

---

## Step 1 — Fix candidate truncation in `combinations.py`

**File**: `src/vn_corrector/stage5_scorer/combinations.py`

### Change

Replace the raw text-extraction loop (lines 28–35):

```python
candidate_lists: list[list[str]] = []
for tc in window.token_candidates:
    texts = [c.text for c in tc.candidates]
    original = tc.token_text
    filtered = [original]
    for t in texts:
        if t != original and len(filtered) < max_per_token:
            filtered.append(t)
    candidate_lists.append(filtered)
```

With sort-by-prior_score:

```python
candidate_lists: list[list[str]] = []
for tc in window.token_candidates:
    # Invariant: position 0 is always the original token;
    # positions 1..N are alternatives sorted by descending prior_score.
    original_texts = [c.text for c in tc.candidates if c.text == tc.token_text][:1]
    alternatives = sorted(
        [c for c in tc.candidates if c.text != tc.token_text],
        key=lambda c: c.prior_score,
        reverse=True,
    )
    texts = original_texts + [c.text for c in alternatives]
    candidate_lists.append(texts[:max_per_token])
```

The downstream truncation at line 43 (`cl[:1] + cl[1:max_per_pos]`) now naturally keeps the best alternatives since they're at the front.

### Add import (no new imports needed — uses existing `Candidate` type from `types.py` already imported via `CandidateWindow`).

---

## Step 2 — Set `edit_distance` in syllable_map source

**File**: `src/vn_corrector/stage4_candidates/sources/syllable_map.py`

### Add import

After line 5 (`from __future__ import annotations`), add:

```python
# TODO: expose a public Vietnamese-aware edit distance utility.
from vn_corrector.stage4_candidates.sources.edit_distance import _levenshtein
```

### Add `edit_distance` to `CandidateProposal`

In the `yield CandidateProposal(...)` block (lines 43–56), add `edit_distance=_levenshtein(request.token_text, entry.surface)`:

```python
yield CandidateProposal(
    text=entry.surface,
    source=CandidateSource.SYLLABLE_MAP,
    evidence=CandidateEvidence(
        source=CandidateSource.SYLLABLE_MAP,
        detail=f"no_tone_key={no_tone}",
        matched_key=no_tone,
        metadata={
            "surface": entry.surface,
            "frequency": freq_val,
        },
    ),
    prior_score=prior_weight + freq_val * 0.2,
    edit_distance=_levenshtein(request.token_text, entry.surface),
)
```

---

## Step 3 — Set `edit_distance` in domain_specific source

**File**: `src/vn_corrector/stage4_candidates/sources/domain_specific.py`

### Add import

After line 5 (`from __future__ import annotations`), add:

```python
# TODO: expose a public Vietnamese-aware edit distance utility.
from vn_corrector.stage4_candidates.sources.edit_distance import _levenshtein
```

### Add `edit_distance` to `CandidateProposal`

In the `yield CandidateProposal(...)` block (lines 70–83), add `edit_distance=_levenshtein(request.token_text, entry.surface)`:

```python
yield CandidateProposal(
    text=entry.surface,
    source=CandidateSource.DOMAIN_SPECIFIC,
    evidence=CandidateEvidence(
        source=CandidateSource.DOMAIN_SPECIFIC,
        detail=f"domain_term: {entry.surface} (domain={domain})",
        matched_key=no_tone,
        metadata={
            "surface": entry.surface,
            "domain": domain,
        },
    ),
    prior_score=prior_weight + freq_val * 0.2,
    edit_distance=_levenshtein(request.token_text, entry.surface),
)
```

---

## Step 4 — Add pruning regression test

**File**: `tests/stage5_scorer/test_combinations.py`

Add to class `TestGenerateSequences`:

```python
def test_truncation_keeps_highest_prior_alternatives(self) -> None:
    """When max_combinations forces pruning, keep best by prior_score, not list order.
    
    Regression for accentless_004: "do" has độ(0.360) as the best candidate
    but it's 4th in storage order; đợ(0.270) is 1st. Without sorting by
    prior_score, độ would be dropped when pruning.
    """
    tcs = [
        _make_tc("neu", ["neu", "nều", "nếu", "nêu"]),
        _make_tc("do", ["do", "đợ", "đỡ", "đờ", "độ", "đỗ", "đổ", "đồ"]),
        _make_tc("am", ["am", "ậm", "ẫm", "ẩm", "ầm", "ấm", "ảm", "ạm"]),
        _make_tc("vua", ["vua", "vừa"]),
        _make_tc("du", ["du", "đủ"]),
    ]
    # Assign higher prior_score to the better alternatives
    for cands in tcs[0].candidates:
        if cands.text == "nếu":
            cands.prior_score = 0.35
        elif cands.text == "nều":
            cands.prior_score = 0.26
        elif cands.text == "nêu":
            cands.prior_score = 0.28
    for cands in tcs[1].candidates:
        if cands.text == "độ":
            cands.prior_score = 0.36
        elif cands.text in ("đồ", "đổ", "đỡ", "đỗ"):
            cands.prior_score = 0.32
        elif cands.text == "đờ":
            cands.prior_score = 0.28
        elif cands.text == "đợ":
            cands.prior_score = 0.27
        elif cands.text == "đũ":
            cands.prior_score = 0.25

    for cands in tcs[2].candidates:
        if cands.text == "ấm":
            cands.prior_score = 0.32
        elif cands.text == "ẩm":
            cands.prior_score = 0.29
        elif cands.text == "ầm":
            cands.prior_score = 0.28
        elif cands.text == "ậm":
            cands.prior_score = 0.26

    for cands in tcs[3].candidates:
        if cands.text == "vừa":
            cands.prior_score = 0.34

    for cands in tcs[4].candidates:
        if cands.text == "đủ":
            cands.prior_score = 0.35

    window = CandidateWindow(start=0, end=5, token_candidates=tcs)
    sequences = generate_sequences(window, max_combinations=100)
    
    # Find which candidates are present for the "do" position (index 1)
    do_position_candidates = {seq.tokens[1] for seq in sequences}
    
    assert "độ" in do_position_candidates, (
        "Best alternative 'độ'(prior=0.36) was pruned; "
        "only got %s" % do_position_candidates
    )
    # When pruning to ~2 per position, the worst alternative should be gone
    assert "đợ" not in do_position_candidates, (
        "Worst alternative 'đợ'(prior=0.27) survived pruning"
    )
```

**Important**: The `_make_tc` helper currently creates candidates with `prior_score=0.0` (no `prior_score` arg). The test above sets scores after construction. Verify the helper signature accepts this approach, or make `_make_tc` accept a `prior_score` parameter.

The `_make_tc` helper from test_combinations.py:
```python
def _make_tc(text: str, candidates: list[str]) -> TokenCandidates:
    return TokenCandidates(
        token_text=text,
        token_index=0,
        protected=False,
        candidates=[
            Candidate(
                text=c,
                normalized=c,
                no_tone_key=c.lower(),
                sources=set(),
                evidence=[],
            )
            for c in candidates
        ],
    )
```

This creates Candidates with `prior_score=0.0` (default). Setting `.prior_score` after construction works because `Candidate` is a `dataclass` (not frozen). The test above sets scores after creation — this is fine.

---

## Step 5 — Add accentless recovery end-to-end test

**File**: `tests/stage5_scorer/test_scorer.py`

Add a new test to `TestPhraseScorer`:

```python
def test_accentless_recovery_with_edit_distance(self, scorer: PhraseScorer) -> None:
    """Corrected accentless phrase outranks identity when edit_distance is set.
    
    Without edit_distance, identity (all spaces unchanged) wins by a large
    margin. With edit_distance=1 for diacritic-restored tokens, the corrected
    sequence should overtake identity.
    """
    tcs = [
        _make_tc(
            "neu",
            [
                ("neu", True, 0, CandidateSource.ORIGINAL),
                ("nếu", False, 1, CandidateSource.SYLLABLE_MAP),
                ("nều", False, 1, CandidateSource.SYLLABLE_MAP),
            ],
        ),
        _make_tc(
            "do",
            [
                ("do", True, 0, CandidateSource.ORIGINAL),
                ("độ", False, 1, CandidateSource.SYLLABLE_MAP),
                ("đợ", False, 1, CandidateSource.SYLLABLE_MAP),
            ],
        ),
        _make_tc(
            "am",
            [
                ("am", True, 0, CandidateSource.ORIGINAL),
                ("ấm", False, 1, CandidateSource.SYLLABLE_MAP),
                ("ậm", False, 1, CandidateSource.SYLLABLE_MAP),
            ],
        ),
        _make_tc(
            "vua",
            [
                ("vua", True, 0, CandidateSource.ORIGINAL),
                ("vừa", False, 1, CandidateSource.SYLLABLE_MAP),
            ],
        ),
        _make_tc(
            "du",
            [
                ("du", True, 0, CandidateSource.ORIGINAL),
                ("đủ", False, 1, CandidateSource.SYLLABLE_MAP),
                ("đụ", False, 1, CandidateSource.SYLLABLE_MAP),
            ],
        ),
    ]
    windows = build_windows(tcs)
    assert len(windows) >= 1
    result = scorer.score_window(windows[0])

    corrected_seq = "nếu độ ấm vừa đủ"
    identity_seq = "neu do am vua du"

    scores = {
        " ".join(s.sequence.tokens): s.score
        for s in result.ranked_sequences
    }

    assert corrected_seq in scores, (
        "Corrected sequence not found in scored sequences. "
        "Available: %s" % list(scores.keys())
    )
    assert identity_seq in scores, "Identity sequence not found"

    assert scores[corrected_seq] > scores[identity_seq], (
        "Corrected sequence (score=%.4f) should outrank identity (score=%.4f) "
        "when edit_distance is set for diacritic-restored tokens"
        % (scores[corrected_seq], scores[identity_seq])
    )
```

---

## Step 6 — Verification

Run in order:

```bash
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```

Address any failures. The edit-distance change in syllable_map/domain_specific may trigger mypy issues about the private import — check if `_levenshtein` needs a `# noqa` or type annotation adjustment.

---

## Expected outcomes

| Case | Before | After |
|---|---|---|
| `test_truncation_keeps_highest_prior_alternatives` | Fails — `độ` is pruned | Passes — `độ` is kept |
| `test_accentless_recovery_with_edit_distance` | Fails — identity wins by ~1.7 points | Passes — corrected wins (edit_distance credit closes the gap) |
| `accentless_004` (manual) | CER after = 0.438 | CER after = 0 (or near-0 if ngram data still missing) |

## What this does NOT fix

- The n-gram data gap. `vừa đủ` is the only ngram entry for this phrase. After this PR, the corrected sequence should outrank identity for 5-token windows, but the decision engine may still need `replace_threshold >= confidence` to accept the change (confidence = `clamp((score + 5) / 10, 0, 1)`). If the score gap is small, verify the decision threshold.
- Other accentless phrases still need ngram data. This fix makes the *general mechanism* work for all diacritic restoration, not just specifically-phrased entries.
