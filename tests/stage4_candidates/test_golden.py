"""Golden regression tests for Stage 4 candidate generation.

Reads ``golden_cases.yaml`` and runs each case against the real
bundled JSON lexicon.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vn_corrector.stage2_lexicon import load_default_lexicon
from vn_corrector.stage4_candidates import CandidateGenerator

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "stage4_candidates"
_GOLDEN_PATH = _FIXTURES / "golden_cases.yaml"


def _load_cases() -> list[dict[str, object]]:
    with open(_GOLDEN_PATH) as f:
        return list(yaml.safe_load(f))


@pytest.fixture(scope="session")
def golden_gen() -> CandidateGenerator:
    lexicon = load_default_lexicon(mode="json")
    return CandidateGenerator(lexicon)


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c.get("description", c["input"]))
def test_golden_case(golden_gen: CandidateGenerator, case: dict[str, object]) -> None:
    protected = case.get("protected", False)
    assert isinstance(protected, bool)
    candidates = golden_gen.generate_token(str(case["input"]), protected=protected)
    texts = {c.text for c in candidates}

    if "expected_exact" in case:
        expected_exact = case["expected_exact"]
        assert isinstance(expected_exact, (list, tuple))
        expected_set: set[str] = set()
        for item in expected_exact:
            assert isinstance(item, str)
            expected_set.add(item)
        assert texts == expected_set, (
            f"Input '{case['input']}': expected exact set {expected_exact}, got {sorted(texts)}"
        )
    elif "expected_contains" in case:
        expected_contains = case["expected_contains"]
        assert isinstance(expected_contains, (list, tuple))
        for expected in expected_contains:
            assert isinstance(expected, str)
            assert expected in texts, (
                f"Input '{case['input']}': expected '{expected}' in candidates, got {sorted(texts)}"
            )

    if "expected_sources" in case:
        expected_sources = case["expected_sources"]
        assert isinstance(expected_sources, dict)
        for text, source_names in expected_sources.items():
            assert isinstance(source_names, list)
            candidate = next((c for c in candidates if c.text == text), None)
            assert candidate is not None, (
                f"Input '{case['input']}': candidate '{text}' not found for source check"
            )
            source_strs = {str(s) for s in candidate.sources}
            for name in source_names:
                assert name in source_strs, (
                    f"Input '{case['input']}', candidate '{text}': "
                    f"expected source '{name}' in {sorted(source_strs)}"
                )
