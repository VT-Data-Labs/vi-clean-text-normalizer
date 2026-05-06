"""Diagnostics helpers for the phrase scorer."""

from __future__ import annotations

from vn_corrector.stage5_scorer.types import ScoredWindow


def format_scored_window(window: ScoredWindow, top_k: int = 5) -> str:
    """Return a human-readable summary of a scored window."""
    lines: list[str] = []
    w = window.window
    tok_texts = [tc.token_text for tc in w.token_candidates]
    lines.append(f"Window [{w.start}:{w.end}]: {' | '.join(tok_texts)}")
    lines.append(f"Ranked sequences (top {top_k}):")

    for i, scored in enumerate(window.ranked_sequences[:top_k]):
        tokens = " ".join(scored.sequence.tokens)
        changed = len(scored.sequence.changed_positions)
        marker = " <<<" if i == 0 else ""
        lines.append(
            f"  {i + 1}. [{scored.score:+.3f}] {tokens}"
            f"  (changed={changed}, conf={scored.confidence:.3f}){marker}"
        )

    if window.best and window.best.explanations:
        lines.append("\nExplanations for best:")
        for exp in window.best.explanations:
            ev_str = "; ".join(f"{e.kind}({e.score_delta:+.3f})" for e in exp.evidence)
            lines.append(f"  [{exp.index}] {exp.original} \u2192 {exp.corrected}: {ev_str}")

    return "\n".join(lines)
