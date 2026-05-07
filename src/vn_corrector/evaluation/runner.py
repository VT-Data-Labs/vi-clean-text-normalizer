from __future__ import annotations

from collections.abc import Callable

from vn_corrector.common.correction import CorrectionResult
from vn_corrector.common.enums import DecisionType
from vn_corrector.evaluation.metrics import cer, wer
from vn_corrector.evaluation.types import (
    EvaluationExample,
    EvaluationReport,
    ExampleEvaluation,
)

CorrectFn = Callable[[str, str | None], CorrectionResult]


def evaluate_examples(
    examples: list[EvaluationExample],
    *,
    correct_fn: CorrectFn,
    dataset_path: str = "",
) -> EvaluationReport:
    """Run evaluation on every example and produce an aggregated report."""
    results = [evaluate_one(example, correct_fn=correct_fn) for example in examples]
    return build_report(results, dataset_path=dataset_path)


def evaluate_one(
    example: EvaluationExample,
    *,
    correct_fn: CorrectFn,
) -> ExampleEvaluation:
    """Evaluate a single example against the correction pipeline."""
    result = correct_fn(example.input, example.domain)
    output = result.corrected_text

    allowed = set(example.allowed_outputs)
    allowed.add(example.expected)

    accepted_output = output in allowed
    changed = output != example.input
    overcorrected = example.should_change is False and changed
    undercorrected = example.should_change is True and not accepted_output

    protected_violation = any(protected not in output for protected in example.protected_substrings)

    accept_count = _decision_count(result, DecisionType.ACCEPT)
    reject_count = _decision_count(result, DecisionType.REJECT)
    flag_count = _decision_count(result, DecisionType.FLAG)
    need_context_count = _decision_count(result, DecisionType.NEED_CONTEXT)

    return ExampleEvaluation(
        id=example.id,
        input=example.input,
        expected=example.expected,
        output=output,
        exact_match=output == example.expected,
        accepted_output=accepted_output,
        cer_before=cer(example.input, example.expected),
        cer_after=cer(output, example.expected),
        wer_before=wer(example.input, example.expected),
        wer_after=wer(output, example.expected),
        changed=changed,
        should_change=example.should_change,
        overcorrected=overcorrected,
        undercorrected=undercorrected,
        protected_violation=protected_violation,
        changes_count=len(result.changes),
        flags_count=len(result.flags),
        accept_count=accept_count,
        reject_count=reject_count,
        flag_count=flag_count,
        need_context_count=need_context_count,
        tags=example.tags,
        domain=example.domain,
    )


def build_report(
    evaluations: list[ExampleEvaluation],
    *,
    dataset_path: str = "",
) -> EvaluationReport:
    """Aggregate a list of ExampleEvaluation into a single EvaluationReport."""
    total = len(evaluations)

    if total == 0:
        return EvaluationReport(
            dataset_path=dataset_path,
            total=0,
            exact_matches=0,
            exact_match_rate=0.0,
            accepted_outputs=0,
            accepted_output_rate=0.0,
            avg_cer_before=0.0,
            avg_cer_after=0.0,
            avg_wer_before=0.0,
            avg_wer_after=0.0,
            cer_improvement=0.0,
            wer_improvement=0.0,
            changed_examples=0,
            overcorrections=0,
            undercorrections=0,
            protected_violations=0,
            avg_changes_per_example=0.0,
            avg_flags_per_example=0.0,
            examples=(),
        )

    exact_matches = sum(1 for e in evaluations if e.exact_match)
    accepted_outputs = sum(1 for e in evaluations if e.accepted_output)
    changed_examples = sum(1 for e in evaluations if e.changed)
    overcorrections = sum(1 for e in evaluations if e.overcorrected)
    undercorrections = sum(1 for e in evaluations if e.undercorrected)
    protected_violations = sum(1 for e in evaluations if e.protected_violation)

    sum_cer_before = sum(e.cer_before for e in evaluations)
    sum_cer_after = sum(e.cer_after for e in evaluations)
    sum_wer_before = sum(e.wer_before for e in evaluations)
    sum_wer_after = sum(e.wer_after for e in evaluations)
    sum_changes = sum(e.changes_count for e in evaluations)
    sum_flags = sum(e.flags_count for e in evaluations)

    avg_cer_before = sum_cer_before / total
    avg_cer_after = sum_cer_after / total
    avg_wer_before = sum_wer_before / total
    avg_wer_after = sum_wer_after / total

    cer_improvement = _safe_improvement(avg_cer_before, avg_cer_after)
    wer_improvement = _safe_improvement(avg_wer_before, avg_wer_after)

    return EvaluationReport(
        dataset_path=dataset_path,
        total=total,
        exact_matches=exact_matches,
        exact_match_rate=exact_matches / total,
        accepted_outputs=accepted_outputs,
        accepted_output_rate=accepted_outputs / total,
        avg_cer_before=avg_cer_before,
        avg_cer_after=avg_cer_after,
        avg_wer_before=avg_wer_before,
        avg_wer_after=avg_wer_after,
        cer_improvement=cer_improvement,
        wer_improvement=wer_improvement,
        changed_examples=changed_examples,
        overcorrections=overcorrections,
        undercorrections=undercorrections,
        protected_violations=protected_violations,
        avg_changes_per_example=sum_changes / total,
        avg_flags_per_example=sum_flags / total,
        examples=tuple(evaluations),
    )


def _decision_count(result: CorrectionResult, decision: DecisionType) -> int:
    return sum(
        1 for c in result.changes if c.decision is not None and c.decision.decision == decision
    )


def _safe_improvement(before: float, after: float) -> float:
    if before == 0.0:
        return 0.0
    return (before - after) / before * 100.0
