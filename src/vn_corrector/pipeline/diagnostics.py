"""Diagnostics and debug output for the correction pipeline."""

from __future__ import annotations

from vn_corrector.common.correction import CorrectionChange, CorrectionResult
from vn_corrector.common.spans import Token
from vn_corrector.stage4_candidates.types import TokenCandidates
from vn_corrector.stage5_scorer.types import CandidateWindow, ScoredWindow


def format_tokens(tokens: list[Token]) -> str:
    """Render a token table for debug output."""
    lines = ["Tokens:"]
    for i, t in enumerate(tokens):
        flags = ""
        if t.protected:
            flags += " [PROTECTED]"
        lines.append(f"  {i:3d} {t.text!r:20s} {t.token_type.value}{flags}")
    return "\n".join(lines)


def format_candidates(token_candidates: list[TokenCandidates]) -> str:
    """Render a per-token candidate list."""
    lines = ["Candidates:"]
    for tc in token_candidates:
        texts = [c.text for c in tc.candidates]
        lines.append(f"  {tc.token_text!r}: {', '.join(texts)}")
    return "\n".join(lines)


def format_window(window: CandidateWindow) -> str:
    """Render a candidate window header."""
    tokens = [tc.token_text for tc in window.token_candidates]
    return f"Window [{window.start}:{window.end}]: {' '.join(tokens)}"


def format_scored_window(scored: ScoredWindow) -> str:
    """Render a scored window with best sequence and confidence."""
    lines = [f"Window [{scored.window.start}:{scored.window.end}]"]
    if scored.best is not None:
        best_tokens = " ".join(scored.best.sequence.tokens)
        lines.append(f"  Best:    {best_tokens!r}")
        lines.append(f"  Score:   {scored.best.score:.4f}")
        lines.append(f"  Conf:    {scored.best.confidence:.4f}")
    else:
        lines.append("  (no ranked sequences)")
    return "\n".join(lines)


def format_change(change: CorrectionChange) -> str:
    """Render a single applied change."""
    sources = ", ".join(s.value for s in change.candidate_sources)
    return (
        f"  [{change.span.start}:{change.span.end}] "
        f"{change.original!r} -> {change.replacement!r} "
        f"(conf={change.confidence:.3f}, src={sources})"
    )


def format_result(result: CorrectionResult) -> str:
    """Render the full correction result for human reading."""
    lines = [
        f"Original:  {result.original_text}",
        f"Corrected: {result.corrected_text}",
        f"Confidence: {result.confidence:.2%}",
    ]
    if result.changes:
        lines.append("Changes:")
        for c in result.changes:
            lines.append(format_change(c))
    if result.flags:
        lines.append("Flags:")
        for f in result.flags:
            lines.append(f"  {f.flag_type}: {f.span_text!r} - {f.reason}")
    return "\n".join(lines)
