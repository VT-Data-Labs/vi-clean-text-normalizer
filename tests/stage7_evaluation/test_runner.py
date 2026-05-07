from __future__ import annotations

from vn_corrector.common.correction import CorrectionResult
from vn_corrector.stage7_evaluation.runner import build_report, evaluate_one
from vn_corrector.stage7_evaluation.types import EvaluationExample, ExampleEvaluation


def _identity_correct(text: str, _domain: str | None = None) -> CorrectionResult:
    return CorrectionResult(
        original_text=text,
        corrected_text=text.strip(),
        confidence=1.0,
    )


def _reverse_correct(text: str, _domain: str | None = None) -> CorrectionResult:
    return CorrectionResult(
        original_text=text,
        corrected_text=text[::-1].strip(),
        confidence=0.5,
    )


class TestEvaluateOne:
    def test_exact_match(self):
        ex = EvaluationExample(id="exact_001", input="hello", expected="hello")
        ev = evaluate_one(ex, correct_fn=_identity_correct)
        assert ev.exact_match is True
        assert ev.accepted_output is True
        assert ev.changed is False
        assert ev.overcorrected is False
        assert ev.undercorrected is False
        assert ev.protected_violation is False
        assert ev.cer_before == 0.0
        assert ev.cer_after == 0.0

    def test_accepted_via_allowed_outputs(self):
        ex = EvaluationExample(
            id="multi_001",
            input="so muong",
            expected="số muỗng",
            allowed_outputs=("số muỗng",),
        )
        ev = evaluate_one(ex, correct_fn=_identity_correct)
        assert ev.exact_match is False
        assert ev.accepted_output is False  # identity doesn't match allowed either

    def test_overcorrection_detected(self):
        ex = EvaluationExample(
            id="over_001",
            input="hello world",
            expected="hello world",
            should_change=False,
        )
        ev = evaluate_one(ex, correct_fn=_reverse_correct)
        assert ev.changed is True
        assert ev.overcorrected is True

    def test_undercorrection_detected(self):
        ex = EvaluationExample(
            id="under_001",
            input="so muong",
            expected="số muỗng",
            should_change=True,
        )
        ev = evaluate_one(ex, correct_fn=_identity_correct)
        assert ev.accepted_output is False
        assert ev.undercorrected is True

    def test_protected_violation_detected(self):
        ex = EvaluationExample(
            id="prot_001",
            input="dt 52m2",
            expected="dt 52m2",
            protected_substrings=("52m2",),
        )
        ev = evaluate_one(ex, correct_fn=_reverse_correct)
        assert ev.protected_violation is True

    def test_no_protected_violation(self):
        ex = EvaluationExample(
            id="safe_001",
            input="dt 52m2",
            expected="dt 52m2",
            protected_substrings=("52m2",),
        )
        ev = evaluate_one(ex, correct_fn=_identity_correct)
        assert ev.protected_violation is False


class TestBuildReport:
    def test_empty_list(self):
        report = build_report([], dataset_path="test.jsonl")
        assert report.total == 0
        assert report.exact_match_rate == 0.0

    def test_all_exact_matches(self):
        evals = [
            ExampleEvaluation(
                id="a",
                input="x",
                expected="x",
                output="x",
                exact_match=True,
                accepted_output=True,
                cer_before=0.0,
                cer_after=0.0,
                wer_before=0.0,
                wer_after=0.0,
                changed=False,
                should_change=False,
                overcorrected=False,
                undercorrected=False,
                protected_violation=False,
                changes_count=0,
                flags_count=0,
            ),
            ExampleEvaluation(
                id="b",
                input="y",
                expected="y",
                output="y",
                exact_match=True,
                accepted_output=True,
                cer_before=0.0,
                cer_after=0.0,
                wer_before=0.0,
                wer_after=0.0,
                changed=False,
                should_change=False,
                overcorrected=False,
                undercorrected=False,
                protected_violation=False,
                changes_count=0,
                flags_count=0,
            ),
        ]
        report = build_report(evals, dataset_path="test.jsonl")
        assert report.total == 2
        assert report.exact_match_rate == 1.0
        assert report.accepted_output_rate == 1.0
        assert report.protected_violations == 0

    def test_mixed_results(self):
        evals = [
            ExampleEvaluation(
                id="good",
                input="x",
                expected="x",
                output="x",
                exact_match=True,
                accepted_output=True,
                cer_before=0.0,
                cer_after=0.0,
                wer_before=0.0,
                wer_after=0.0,
                changed=False,
                should_change=False,
                overcorrected=False,
                undercorrected=False,
                protected_violation=False,
                changes_count=0,
                flags_count=0,
            ),
            ExampleEvaluation(
                id="bad",
                input="z",
                expected="w",
                output="q",
                exact_match=False,
                accepted_output=False,
                cer_before=1.0,
                cer_after=1.0,
                wer_before=1.0,
                wer_after=1.0,
                changed=True,
                should_change=True,
                overcorrected=False,
                undercorrected=True,
                protected_violation=True,
                changes_count=2,
                flags_count=1,
            ),
        ]
        report = build_report(evals, dataset_path="test.jsonl")
        assert report.total == 2
        assert report.exact_match_rate == 0.5
        assert report.accepted_output_rate == 0.5
        assert report.overcorrections == 0
        assert report.undercorrections == 1
        assert report.protected_violations == 1
        assert report.avg_changes_per_example == 1.0
        assert report.avg_flags_per_example == 0.5
