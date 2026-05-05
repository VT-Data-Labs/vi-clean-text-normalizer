# Agent Instructions

## Source of truth

Read `PROJECT.md` before making changes. If your implementation conflicts with `PROJECT.md`, stop and explain the conflict.

## Coding rules

- Prefer modifying existing modules over creating new ones.
- Search for existing constants, helpers, validators, and types before adding new ones.
- Shared constants belong in `src/vn_corrector/common/constants.py`.
- Shared errors belong in `src/vn_corrector/common/errors.py`.
- Shared type definitions belong in `src/vn_corrector/common/types.py`.
- Shared validation helpers belong in `src/vn_corrector/common/validation.py`.
- Avoid duplicated logic. Code duplication longer than 5 lines is not allowed without justification.
- Do not weaken tests to make them pass.
- Do not remove error handling or validation unless explicitly required.
- Keep diffs small and reviewable.

## Testing rules

Every behavior change must include tests.

Required before completion:

```bash
pytest
pylint src tests
```

If a command fails, report the failure clearly and do not claim the task is complete.

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

This project is indexed by GitNexus as **vi-clean-text-normalizer** (73 symbols, 71 relationships, 0 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
