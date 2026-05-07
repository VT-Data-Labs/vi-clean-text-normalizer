from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vn_corrector.evaluation.types import EvaluationExample


def load_jsonl(path: str | Path) -> list[EvaluationExample]:
    """Load evaluation examples from a JSONL file.

    Each line must be a JSON object with at least ``id``, ``input``,
    and ``expected`` fields.  Blank lines are skipped.
    """
    examples: list[EvaluationExample] = []
    resolved = Path(path)

    with resolved.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                msg = f"{resolved}:{line_no}: invalid JSON: {exc}"
                raise ValueError(msg) from exc

            examples.append(parse_example(data, path=str(resolved), line_no=line_no))

    return examples


def parse_example(data: dict[str, Any], *, path: str, line_no: int) -> EvaluationExample:
    """Parse a single JSON object into an EvaluationExample.

    Validates that ``id``, ``input``, and ``expected`` are present.
    """
    for field in ("id", "input", "expected"):
        if field not in data:
            msg = f"{path}:{line_no}: missing required field {field!r}"
            raise ValueError(msg)

    return EvaluationExample(
        id=str(data["id"]),
        input=str(data["input"]),
        expected=str(data["expected"]),
        allowed_outputs=tuple(data.get("allowed_outputs") or ()),
        domain=data.get("domain"),
        tags=tuple(data.get("tags") or ()),
        should_change=data.get("should_change"),
        protected_substrings=tuple(data.get("protected_substrings") or ()),
        notes=data.get("notes"),
    )
