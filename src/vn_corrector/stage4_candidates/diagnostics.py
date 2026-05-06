"""Diagnostics helpers for Stage 4 — Candidate Generation.

Provides explainability: human-readable descriptions of why each
candidate exists, which sources contributed, and any trimming events.
"""

from __future__ import annotations

from vn_corrector.stage4_candidates.types import (
    Candidate,
    CandidateDocument,
    TokenCandidates,
)


def format_candidate_debug(candidate: Candidate) -> list[str]:
    """Return human-readable diagnostic lines for a single candidate."""
    lines: list[str] = []
    lines.append(f"  text='{candidate.text}' prior={candidate.prior_score:.3f}")
    lines.append(f"    normalized='{candidate.normalized}' no_tone='{candidate.no_tone_key}'")
    sources_str = ", ".join(str(s) for s in sorted(candidate.sources))
    lines.append(f"    sources=[{sources_str}]")
    lines.append(f"    is_original={candidate.is_original} lex_freq={candidate.lexicon_freq:.4f}")
    if candidate.edit_distance is not None:
        lines.append(f"    edit_distance={candidate.edit_distance}")
    if candidate.replacement_token_count > 1:
        lines.append(f"    replacement_token_count={candidate.replacement_token_count}")
    if candidate.evidence:
        lines.append("    evidence:")
        for ev in candidate.evidence:
            lines.append(f"      [{ev.source!s}] {ev.detail}")
    return lines


def format_token_candidates_debug(tc: TokenCandidates) -> list[str]:
    """Generate debug lines for a TokenCandidates block."""
    lines: list[str] = []
    lines.append(
        f"TokenCandidates[idx={tc.token_index}] text='{tc.token_text}' protected={tc.protected}"
    )
    if tc.diagnostics:
        for diag in tc.diagnostics:
            lines.append(f"  diag: {diag}")
    lines.append(f"  candidates ({len(tc.candidates)}):")
    for candidate in tc.candidates:
        lines.extend(format_candidate_debug(candidate))
    return lines


def format_document_debug(doc: CandidateDocument) -> str:
    """Generate a full debug string for a CandidateDocument."""
    lines: list[str] = []
    lines.append("=== CandidateDocument Debug ===")
    lines.append(f"Stats: {doc.stats}")
    lines.append("")
    for tc in doc.token_candidates:
        lines.extend(format_token_candidates_debug(tc))
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "format_candidate_debug",
    "format_document_debug",
    "format_token_candidates_debug",
]
