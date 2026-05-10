---
name: feature-module-development
description: Workflow command scaffold for feature-module-development in vi-clean-text-normalizer.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /feature-module-development

Use this workflow when working on **feature-module-development** in `vi-clean-text-normalizer`.

## Goal

Implements a new major pipeline stage or feature module, including core implementation, configuration, and comprehensive tests.

## Common Files

- `src/vn_corrector/stage*/__init__.py`
- `src/vn_corrector/stage*/*.py`
- `tests/stage*/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create new module directory under src/vn_corrector/stageX_*/ or src/vn_corrector/feature/
- Add core implementation files (e.g., .py for logic, config, types)
- Add or update configuration files (config.py, types.py, etc.)
- Add or update test files in tests/stageX_*/ or tests/feature/
- Integrate with pipeline or CLI if needed

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.