"""Explainability helpers for the phrase scorer."""

from __future__ import annotations

from vn_corrector.stage5_scorer.types import ScoredSequence


def format_explanation(scored: ScoredSequence) -> str:
    """Return a human-readable explanation for a scored sequence."""
    lines: list[str] = []
    lines.append(f"Score: {scored.score:.3f}  Confidence: {scored.confidence:.3f}")
    lines.append(f"Original: {' '.join(scored.sequence.original_tokens)}")
    lines.append(f"Corrected: {' '.join(scored.sequence.tokens)}")

    if not scored.explanations:
        lines.append("No changes applied.")
        return "\n".join(lines)

    for exp in scored.explanations:
        lines.append(f"\nToken [{exp.index}]: {exp.original} \u2192 {exp.corrected}")
        for ev in exp.evidence:
            delta = f" ({ev.score_delta:+.3f})" if ev.score_delta else ""
            lines.append(f"  \u2022 {ev.kind}: {ev.message}{delta}")

    lines.append("\nScoreBreakdown:")
    b = scored.breakdown
    lines.append(f"  word_validity:          {b.word_validity:+.3f}")
    lines.append(f"  syllable_freq:          {b.syllable_freq:+.3f}")
    lines.append(f"  phrase_ngram:           {b.phrase_ngram:+.3f}")
    lines.append(f"  domain_context:         {b.domain_context:+.3f}")
    lines.append(f"  ocr_confusion:          {b.ocr_confusion:+.3f}")
    lines.append(f"  edit_distance:          {b.edit_distance:+.3f}")
    lines.append(f"  overcorrection_penalty:  {b.overcorrection_penalty:+.3f}")
    lines.append(f"  negative_phrase_penalty: {b.negative_phrase_penalty:+.3f}")
    lines.append(f"  {'─' * 29}")
    lines.append(f"  total:                  {b.total:+.3f}")
    return "\n".join(lines)
