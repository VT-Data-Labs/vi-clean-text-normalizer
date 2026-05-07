from __future__ import annotations

import json
from pathlib import Path

import pytest

from vn_corrector.stage7_evaluation.dataset import load_jsonl, parse_example


def test_parse_example_minimal():
    data = {"id": "test_001", "input": "hello", "expected": "world"}
    ex = parse_example(data, path="test.jsonl", line_no=1)
    assert ex.id == "test_001"
    assert ex.input == "hello"
    assert ex.expected == "world"
    assert ex.allowed_outputs == ()
    assert ex.domain is None
    assert ex.tags == ()
    assert ex.should_change is None
    assert ex.protected_substrings == ()
    assert ex.notes is None


def test_parse_example_full():
    data = {
        "id": "full_001",
        "input": "so muong",
        "expected": "số muỗng",
        "allowed_outputs": ["số muỗng", "số muống"],
        "domain": "real_estate",
        "tags": ["accentless", "real_estate"],
        "should_change": True,
        "protected_substrings": ["muỗng"],
        "notes": "test note",
    }
    ex = parse_example(data, path="test.jsonl", line_no=2)
    assert ex.id == "full_001"
    assert ex.allowed_outputs == ("số muỗng", "số muống")
    assert ex.domain == "real_estate"
    assert ex.tags == ("accentless", "real_estate")
    assert ex.should_change is True
    assert ex.protected_substrings == ("muỗng",)
    assert ex.notes == "test note"


def test_parse_example_missing_id():
    data = {"input": "x", "expected": "y"}
    with pytest.raises(ValueError, match="missing required field 'id'"):
        parse_example(data, path="test.jsonl", line_no=3)


def test_parse_example_missing_input():
    data = {"id": "x", "expected": "y"}
    with pytest.raises(ValueError, match="missing required field 'input'"):
        parse_example(data, path="test.jsonl", line_no=4)


def test_parse_example_missing_expected():
    data = {"id": "x", "input": "y"}
    with pytest.raises(ValueError, match="missing required field 'expected'"):
        parse_example(data, path="test.jsonl", line_no=5)


def test_load_jsonl_empty(tmp_path: Path) -> None:
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    assert load_jsonl(f) == []


def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "blank.jsonl"
    f.write_text("\n\n\n")
    assert load_jsonl(f) == []


def test_load_jsonl_valid(tmp_path: Path) -> None:
    f = tmp_path / "valid.jsonl"
    f.write_text(
        json.dumps({"id": "a", "input": "x", "expected": "y"})
        + "\n"
        + json.dumps({"id": "b", "input": "z", "expected": "w"})
        + "\n"
    )
    examples = load_jsonl(f)
    assert len(examples) == 2
    assert examples[0].id == "a"
    assert examples[1].id == "b"


def test_load_jsonl_invalid_json(tmp_path: Path) -> None:
    f = tmp_path / "invalid.jsonl"
    f.write_text("{invalid}\n")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_jsonl(f)


def test_load_jsonl_line_error_context(tmp_path: Path) -> None:
    f = tmp_path / "context.jsonl"
    f.write_text(
        json.dumps({"id": "a", "input": "x", "expected": "y"})
        + "\n"
        + "garbage\n"
        + json.dumps({"id": "b", "input": "z", "expected": "w"})
        + "\n"
    )
    with pytest.raises(ValueError, match=r"context\.jsonl:2"):
        load_jsonl(f)
