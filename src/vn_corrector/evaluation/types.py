from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EvaluationExample:
    id: str
    input: str
    expected: str
    allowed_outputs: tuple[str, ...] = field(default_factory=tuple)
    domain: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    should_change: bool | None = None
    protected_substrings: tuple[str, ...] = field(default_factory=tuple)
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ExampleEvaluation:
    id: str
    input: str
    expected: str
    output: str

    exact_match: bool
    accepted_output: bool

    cer_before: float
    cer_after: float
    wer_before: float
    wer_after: float

    changed: bool
    should_change: bool | None
    overcorrected: bool
    undercorrected: bool
    protected_violation: bool

    changes_count: int
    flags_count: int
    accept_count: int = 0
    reject_count: int = 0
    flag_count: int = 0
    need_context_count: int = 0

    tags: tuple[str, ...] = field(default_factory=tuple)
    domain: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    dataset_path: str
    total: int

    exact_matches: int
    exact_match_rate: float
    accepted_outputs: int
    accepted_output_rate: float

    avg_cer_before: float
    avg_cer_after: float
    avg_wer_before: float
    avg_wer_after: float

    cer_improvement: float
    wer_improvement: float

    changed_examples: int
    overcorrections: int
    undercorrections: int
    protected_violations: int

    avg_changes_per_example: float
    avg_flags_per_example: float

    examples: tuple[ExampleEvaluation, ...]
