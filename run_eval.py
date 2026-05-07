"""Load gold.small.jsonl, run evaluate_examples, print per-example results."""

import json

from vn_corrector.pipeline.corrector import correct_text
from vn_corrector.stage7_evaluation.runner import evaluate_examples
from vn_corrector.stage7_evaluation.types import EvaluationExample

with open("data/evaluation/gold.small.jsonl") as f:
    examples: list[EvaluationExample] = []
    for line in f:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        examples.append(
            EvaluationExample(
                id=d["id"],
                input=d["input"],
                expected=d["expected"],
                allowed_outputs=tuple(d.get("allowed_outputs", [])),
                domain=d.get("domain"),
                tags=tuple(d.get("tags", [])),
                should_change=d.get("should_change"),
                protected_substrings=tuple(d.get("protected_substrings", [])),
                notes=d.get("notes"),
            )
        )

report = evaluate_examples(
    examples,
    correct_fn=correct_text,
    dataset_path="data/evaluation/gold.small.jsonl",
)

for ev in report.examples:
    status = "ACCEPTED" if ev.accepted_output else "REJECTED"
    print(
        f"{ev.id:30s} | {status:9s} | "
        f"input=      {ev.input!r}\n"
        f"{'':30s} | {'':9s} | "
        f"output=     {ev.output!r}\n"
        f"{'':30s} | {'':9s} | "
        f"expected=   {ev.expected!r}\n"
        f"{'':30s} | {'':9s} | "
        f"allowed=    {ev.expected!r}"
    )
    if ev.accepted_output and ev.output != ev.expected:
        for a in examples:
            if a.id == ev.id:
                allowed = list(a.allowed_outputs)
                if allowed:
                    print(f"{'':30s} | {'':9s} | allowed_extra={allowed!r}")
                break
    print()

print(f"\n{'=' * 80}")
print(
    f"Total: {report.total} | "
    f"Exact: {report.exact_matches} ({report.exact_match_rate:.1%}) | "
    f"Accepted: {report.accepted_outputs} ({report.accepted_output_rate:.1%})"
)
print(f"{'=' * 80}")
