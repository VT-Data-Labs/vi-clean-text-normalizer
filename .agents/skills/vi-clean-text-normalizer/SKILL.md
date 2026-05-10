```markdown
# vi-clean-text-normalizer Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns, coding conventions, and workflows used in the `vi-clean-text-normalizer` Python codebase. You'll learn how to structure new features, refactor modules, update data pipelines, write and organize tests, and maintain documentation in a collaborative, maintainable way. The repository focuses on modular, pipeline-based Vietnamese text normalization, with an emphasis on clarity, test coverage, and well-documented changes.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files and modules.
  ```
  # Good
  src/vn_corrector/stage2_lexicon/lexicon_store.py

  # Bad
  src/vn_corrector/stage2Lexicon/LexiconStore.py
  ```

- **Import Style:**  
  Use **relative imports** within packages.
  ```python
  # Good
  from .types import LexiconEntry

  # Bad
  from vn_corrector.stage2_lexicon.types import LexiconEntry
  ```

- **Export Style:**  
  Use **named exports**; explicitly define what is exported from each module.
  ```python
  # In __init__.py
  from .lexicon_store import LexiconStore

  __all__ = ["LexiconStore"]
  ```

- **Commit Messages:**  
  Use prefixes such as `chore:`, `docs:`, `refactor:`, `fix:`, `feat:`, `m3:`.  
  Keep commit messages concise (average ~62 characters).
  ```
  feat: add candidate generator for stage3
  fix: handle edge case in ngram scorer
  ```

## Workflows

### Feature Module Development
**Trigger:** When adding a new pipeline stage or major feature (e.g., candidate generator, scorer, decision engine, evaluation harness).  
**Command:** `/new-feature-module`

1. Create a new module directory under `src/vn_corrector/stageX_*/` or `src/vn_corrector/feature/`.
2. Add core implementation files (`.py` for logic, `config.py`, `types.py`, etc.).
3. Add or update configuration files as needed.
4. Add or update test files in `tests/stageX_*/` or `tests/feature/`.
5. Integrate the new module with the pipeline or CLI if required.

**Example:**
```bash
mkdir src/vn_corrector/stage4_candidate_generator
touch src/vn_corrector/stage4_candidate_generator/__init__.py
touch src/vn_corrector/stage4_candidate_generator/generator.py
touch tests/stage4_candidate_generator/test_generator.py
```

---

### Design Docs Before Implementation
**Trigger:** When planning a new major feature or pipeline stage.  
**Command:** `/new-design-doc`

1. Create a design spec in `docs/superpowers/specs/*.md`.
2. Create an implementation plan in `docs/superpowers/plans/*.md`.
3. Reference or link these docs in the related feature PR or commit.

**Example:**
```bash
touch docs/superpowers/specs/candidate_generator.md
touch docs/superpowers/plans/candidate_generator_plan.md
```

---

### Refactor Module Restructure
**Trigger:** When improving codebase structure, disambiguating types, or merging/splitting modules.  
**Command:** `/refactor-module`

1. Move or rename files/directories (e.g., `lexicon/`, `evaluation/`, `types.py`).
2. Update all imports and references across the codebase.
3. Update related test files to match new structure.
4. Update documentation if needed.

**Example:**
```bash
mv src/vn_corrector/lexicon src/vn_corrector/lexicons
# Update imports: from .lexicon -> from .lexicons
```

---

### Add or Update Tests for Feature
**Trigger:** When implementing a new feature or fixing a bug.  
**Command:** `/add-tests`

1. Add or update test files in `tests/` matching the feature/module.
2. Add regression, acceptance, or golden tests as needed.
3. Ensure tests cover new code paths.

**Example:**
```bash
touch tests/stage2_lexicon/test_lexicon_store.py
# Add test cases for new logic or bug fixes
```

---

### Data Pipeline Update
**Trigger:** When updating lexicon sources, ngram data, or data build scripts.  
**Command:** `/update-data-pipeline`

1. Update or add data files in `data/` or `resources/`.
2. Update or add build scripts in `scripts/`.
3. Regenerate processed data artifacts (e.g., `.db`, `.json`).
4. Update code to use new data or schema if needed.
5. Update or add tests to validate new data.

**Example:**
```bash
python scripts/build_lexicon_db.py
# Commit updated data/lexicon/lexicon.db and related tests
```

---

### Documentation Update for Feature or Release
**Trigger:** When a new feature is added, module layout changes, or a milestone is reached.  
**Command:** `/update-docs`

1. Edit `README.md`, `AGENTS.md`, or `DEVELOPMENT.md`.
2. Document new features, modules, or code quality rules.
3. Update diagrams, status checklists, or example outputs.

**Example:**
```bash
vim README.md
# Add description of new candidate generator module
```

## Testing Patterns

- **Test File Location:**  
  Place test files in `tests/stageX_*/`, `tests/feature/`, or other relevant subdirectories.
- **Test Naming:**  
  Use descriptive names matching the module under test, e.g., `test_lexicon_store.py`.
- **Test Coverage:**  
  Add regression, acceptance, or golden tests as appropriate for new features or bug fixes.
- **Framework:**  
  While the specific framework is not detected, use standard Python testing frameworks (e.g., `pytest` or `unittest`).

**Example:**
```python
# tests/stage2_lexicon/test_lexicon_store.py
import pytest
from src.vn_corrector.stage2_lexicon.lexicon_store import LexiconStore

def test_lookup_existing_word():
    store = LexiconStore("data/lexicon/lexicon.db")
    assert store.lookup("xin") == "xin"
```

## Commands

| Command                | Purpose                                                      |
|------------------------|--------------------------------------------------------------|
| /new-feature-module    | Start a new pipeline stage or major feature module           |
| /new-design-doc        | Create a design spec and implementation plan                 |
| /refactor-module       | Move, split, or rename modules for clarity/maintainability   |
| /add-tests             | Add or update tests for a feature or bugfix                  |
| /update-data-pipeline  | Update or rebuild data artifacts and synchronize scripts     |
| /update-docs           | Update documentation for new features or releases            |
```