from __future__ import annotations

from pathlib import Path

from vn_corrector.cli import correct_text
from vn_corrector.stage7_evaluation.dataset import load_jsonl
from vn_corrector.stage7_evaluation.runner import evaluate_examples

_HERE = Path(__file__).resolve().parent
_SMALL_DATASET = str(_HERE.parent.parent / "data" / "evaluation" / "gold.small.jsonl")


def test_gold_small_regression():
    examples = load_jsonl(_SMALL_DATASET)
    report = evaluate_examples(examples, correct_fn=correct_text, dataset_path=_SMALL_DATASET)

    # Thresholds are deliberately loose for the stub correct_text().
    # Raise them as the pipeline improves:
    #   accepted_output_rate → 0.80+
    #   overcorrections → 0
    assert report.protected_violations == 0, f"Got {report.protected_violations} violations"
    assert report.total > 0, "Dataset is empty"
    assert report.accepted_output_rate >= 0.20, f"Accepted rate: {report.accepted_output_rate:.2%}"
    assert report.overcorrections <= 3, f"Overcorrections: {report.overcorrections}"
