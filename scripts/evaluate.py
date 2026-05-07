#!/usr/bin/env python3
"""Evaluation harness CLI for the Vietnamese correction pipeline.

Usage:
    python scripts/evaluate.py data/evaluation/gold.small.jsonl
    python scripts/evaluate.py data/evaluation/gold.small.jsonl --json
    python scripts/evaluate.py data/evaluation/gold.small.jsonl --fail-under-accepted 0.60
"""

from __future__ import annotations

import argparse
import sys

from vn_corrector.common.correction import CorrectionResult
from vn_corrector.evaluation.dataset import load_jsonl
from vn_corrector.evaluation.report import format_report, report_to_json
from vn_corrector.evaluation.runner import evaluate_examples


def _correct_text(text: str, domain: str | None = None) -> CorrectionResult:
    """Run a single correction using the pipeline's correct_text."""
    from vn_corrector.cli import correct_text

    return correct_text(text, domain)


def main() -> int:
    """Run evaluation and optionally fail CI based on thresholds."""
    parser = argparse.ArgumentParser(
        description="Evaluate the Vietnamese correction pipeline against gold data.",
    )
    parser.add_argument("dataset", help="Path to gold JSONL dataset file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--fail-under-accepted",
        type=float,
        default=None,
        help="Fail CI if accepted_output_rate is below this threshold (0-1)",
    )
    parser.add_argument(
        "--fail-over-overcorrection",
        type=float,
        default=None,
        help="Fail CI if overcorrection rate exceeds this threshold (0-1)",
    )
    parser.add_argument(
        "--fail-over-protected",
        type=int,
        default=None,
        help="Fail CI if protected violations exceed this count",
    )

    args = parser.parse_args()

    examples = load_jsonl(args.dataset)
    report = evaluate_examples(
        examples,
        correct_fn=_correct_text,
        dataset_path=args.dataset,
    )

    if args.json:
        print(report_to_json(report))
    else:
        print(format_report(report))

    threshold = args.fail_under_accepted
    if threshold is not None and report.accepted_output_rate < threshold:
        print(
            f"\nFAIL: accepted_output_rate {report.accepted_output_rate:.2%} < {threshold:.0%}",
            file=sys.stderr,
        )
        return 1

    if args.fail_over_overcorrection is not None:
        over_rate = report.overcorrections / report.total if report.total else 0.0
        if over_rate > args.fail_over_overcorrection:
            print(
                f"\nFAIL: overcorrection rate {over_rate:.2%} > "
                f"{args.fail_over_overcorrection:.0%}",
                file=sys.stderr,
            )
            return 1

    max_violations = args.fail_over_protected
    if max_violations is not None and report.protected_violations > max_violations:
        print(
            f"\nFAIL: protected violations {report.protected_violations} > {max_violations}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
