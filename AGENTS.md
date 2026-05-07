# Agent Instructions

## Source of truth

Read `PROJECT.md` before making changes. If your implementation conflicts with `PROJECT.md`, stop and explain the conflict.

## Tooling

- **Python 3.12+** (see `.python-version`), managed with **uv**.
- Dev install: `uv sync --all-extras`
- CI install: `uv sync --frozen --all-extras`
- Run CLI: `uv run corrector "text"`, or `corrector candidates "người dẫn"`, or `corrector lexicon lookup muỗng` (entrypoint: `vn_corrector.cli:main`)
- Formatter: `ruff format src tests`
- CI order (also the pre-commit order): `ruff check` → `ruff format --check` → `mypy` → `pytest`
- Coverage on by default via `pyproject.toml` (`pytest` always runs with `--cov`)

## Package architecture

Single package `vn_corrector` under `src/vn_corrector/`. No external runtime dependencies — zero runtime deps in `pyproject.toml`. All dev-only.

Top-level modules: `cli.py`, `normalizer.py`, `tokenizer.py`, `case_mask.py`, `protected_tokens.py`. Stage packages live under `stage1_normalize/` through `stage6_decision/`.

Tests mirror the source layout under `tests/` (e.g., `tests/stage4_candidates/`, `tests/stage5_scorer/`). Golden YAML regression suite at `tests/fixtures/stage4_candidates/golden_cases.yaml`.

## Coding rules

- **DRY — Do Not Repeat Yourself.** Build a single canonical implementation in a generic module, then import it everywhere. Never copy-paste logic across files.
- Search for existing constants, helpers, validators, and types before adding new ones.
- **If a function exists in `stage1_normalize/` or `common/`, import it — do not reimplement.**
- Prefer modifying existing modules over creating new ones.
- **Use abstract base classes (ABC), never `Protocol`** — shared interfaces must inherit from `ABC` with `@abstractmethod`. No `from typing import Protocol`.
- **No `Any` or `object` as type annotations** — use concrete types, generic types (`list[str]`, `dict[str, int]`), or union types (`str | int`). Sentinels (`_SENTINEL = object()`) are the only exception.
- **No `# type: ignore` or `# noqa` suppression comments** — fix the underlying type or lint issue instead. (Existing violations in `json_store.py` and `cli.py` are accepted tech debt; new code must not add more.)

### Shared module locations

| Concern | Canonical location |
|---|---|
| Vietnamese char normalization (strip_accents, fix_lookalikes, normalize_text, normalize_key) | `src/vn_corrector/stage1_normalize/char_normalizer.py` |
| Stage 1 pipeline (full text normalization) | `src/vn_corrector/stage1_normalize/engine.py` |
| Shared constants | `src/vn_corrector/common/constants.py` |
| Shared errors | `src/vn_corrector/common/errors.py` |
| Shared type definitions | `src/vn_corrector/common/types.py` |
| Shared validation helpers | `src/vn_corrector/common/validation.py` |

### Vietnamese character normalization — single source of truth

All Vietnamese accent stripping, Unicode lookalike fixing, and text normalisation **must** live exclusively in
`src/vn_corrector/stage1_normalize/char_normalizer.py`.

Functions available (import from ``vn_corrector.stage1_normalize``):

- ``strip_accents()`` — lowercase + strip tone marks
- ``strip_accents_preserve_case()`` — strip tone marks, keep casing
- ``to_no_tone_key()`` — stable no-tone lookup key
- ``fix_lookalikes()`` — correct Icelandic eth → đ, o-breve → ơ, curly quotes, etc.
- ``normalize_text()`` — NFC + fix_lookalikes + lowercase + collapse whitespace
- ``normalize_key()`` — canonical lexicon key (accentless + whitespace-collapsed)
- ``VIETNAMESE_ACCENT_MAP`` — codepoint → base letter dict

**Rule:** Any module that needs to strip accents, normalise Vietnamese text, or
generate no-tone keys **must import** from ``vn_corrector.stage1_normalize``.
Standalone copies of these functions are forbidden.

Backward-compat shims exist at ``vn_corrector.stage2_lexicon.core.accent_stripper``
and ``stage2_lexicon.core.normalize`` for migration. New code **must not** use them.

### General DRY rules

- Shared constants belong in `src/vn_corrector/common/constants.py`.
- Shared errors belong in `src/vn_corrector/common/errors.py`.
- Shared type definitions belong in `src/vn_corrector/common/types.py`.
- Shared validation helpers belong in `src/vn_corrector/common/validation.py`.
- **Code duplication longer than 5 lines is not allowed** without justification in a comment.
- **Scripts in `scripts/` must import from `src/`** — standalone copies of core logic in scripts are forbidden.
- Do not weaken tests to make them pass.
- Do not remove error handling or validation unless explicitly required.
- Keep diffs small and reviewable.

## Resources and data

- **Lexicons**: `resources/lexicons/` — 9 JSON files (syllables, words, phrases, units, abbreviations, ocr_confusions, foreign_words, chemicals, lexicon_package)
- **N-grams**: `resources/ngrams/ngram_store.vi.json` — bigrams and trigrams with confidence scores
- **Build scripts**: `scripts/` includes `build_lexicon_db.py`, `build_trusted_lexicon.py`, `build_ngram_store.py`, `download_lexicon_sources.py`
- `scripts/build_lexicon_db.py` and `scripts/build_trusted_lexicon.py` are excluded from mypy (see `pyproject.toml` overrides)
- Generated artifacts `resources/lexicons/lexicon_package.json` and `resources/lexicon/trusted_words.vi.jsonl` are gitignored

## Testing rules

Every behavior change must include tests.

Required before completion:

```bash
ruff check src tests
ruff format --check src tests
mypy src tests
pytest
```

If a command fails, report the failure clearly and do not claim the task is complete.

## Committing

Do not add co-author lines to commits. Commit messages must be plain (no generated trailers).

## Review rules

Before final response, summarize:

- files changed
- tests added/updated
- commands run
- remaining risks
- suggested follow-up refactors

---

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **vi-clean-text-normalizer** (3781 symbols, 6423 relationships, 64 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/vi-clean-text-normalizer/context` | Codebase overview, check index freshness |
| `gitnexus://repo/vi-clean-text-normalizer/clusters` | All functional areas |
| `gitnexus://repo/vi-clean-text-normalizer/processes` | All execution flows |
| `gitnexus://repo/vi-clean-text-normalizer/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->

---

<!-- guidelines:start -->

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


<!-- guidelines:end -->
