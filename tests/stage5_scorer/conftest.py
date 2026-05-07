"""Pytest configuration for stage5_scorer tests."""

from __future__ import annotations

import sys
from pathlib import Path

# pytest adds the test file's parent directory to sys.path[0].
# For tests in tests/stage5_scorer/ this means sys.path[0] = tests/stage5_scorer/,
# NOT the repo root.  Add the repo root so that ``scripts/`` is importable.
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
