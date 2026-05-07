from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from vn_corrector.stage7_evaluation.types import EvaluationReport


def format_report(report: EvaluationReport) -> str:
    """Format an EvaluationReport as human-readable text."""
    accepted_line = (
        f"Accepted output: {report.accepted_outputs} / {report.total}"
        f" = {report.accepted_output_rate:.2%}"
    )
    exact_line = (
        f"Exact match:     {report.exact_matches} / {report.total} = {report.exact_match_rate:.2%}"
    )
    lines = [
        "Evaluation Report",
        "=" * 60,
        "",
        f"Dataset: {report.dataset_path}",
        f"Examples: {report.total}",
        "",
        accepted_line,
        exact_line,
        "",
        "CER:",
        f"  before:       {report.avg_cer_before:.4f}",
        f"  after:        {report.avg_cer_after:.4f}",
        f"  improvement:  {report.cer_improvement:.2f}%",
        "",
        "WER:",
        f"  before:       {report.avg_wer_before:.4f}",
        f"  after:        {report.avg_wer_after:.4f}",
        f"  improvement:  {report.wer_improvement:.2f}%",
        "",
        "Behavior:",
        f"  changed examples:       {report.changed_examples}",
        f"  overcorrections:        {report.overcorrections}",
        f"  undercorrections:       {report.undercorrections}",
        f"  protected violations:   {report.protected_violations}",
        f"  avg changes per ex:     {report.avg_changes_per_example:.2f}",
        f"  avg flags per ex:       {report.avg_flags_per_example:.2f}",
    ]

    failures = [e for e in report.examples if not e.accepted_output]
    if failures:
        lines.extend(["", "Worst examples:"])
        for ex in sorted(failures, key=lambda e: e.cer_after, reverse=True)[:5]:
            lines.append(f"  {ex.id}")
            lines.append(f"    input:    {ex.input}")
            lines.append(f"    expected: {ex.expected}")
            lines.append(f"    output:   {ex.output}")
            lines.append(f"    CER after: {ex.cer_after:.3f}")
            lines.append("")

    return "\n".join(lines)


def report_to_json(report: EvaluationReport) -> str:
    """Serialize an EvaluationReport to pretty-printed JSON."""
    data = _report_asdict(report)
    return json.dumps(data, ensure_ascii=False, indent=2)


def _report_asdict(report: EvaluationReport) -> dict[str, Any]:
    return {
        "dataset_path": report.dataset_path,
        "total": report.total,
        "exact_matches": report.exact_matches,
        "exact_match_rate": report.exact_match_rate,
        "accepted_outputs": report.accepted_outputs,
        "accepted_output_rate": report.accepted_output_rate,
        "avg_cer_before": report.avg_cer_before,
        "avg_cer_after": report.avg_cer_after,
        "avg_wer_before": report.avg_wer_before,
        "avg_wer_after": report.avg_wer_after,
        "cer_improvement": report.cer_improvement,
        "wer_improvement": report.wer_improvement,
        "changed_examples": report.changed_examples,
        "overcorrections": report.overcorrections,
        "undercorrections": report.undercorrections,
        "protected_violations": report.protected_violations,
        "avg_changes_per_example": report.avg_changes_per_example,
        "avg_flags_per_example": report.avg_flags_per_example,
        "examples": [asdict(e) for e in report.examples],
    }
