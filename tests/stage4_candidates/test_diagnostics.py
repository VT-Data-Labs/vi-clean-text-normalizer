"""Tests for diagnostics helpers — explainable debug output.

Verifies that format_candidate_debug, format_token_candidates_debug,
and format_document_debug produce human-readable, accurate output.
"""

from __future__ import annotations

from vn_corrector.stage4_candidates import (
    CandidateDocument,
    CandidateGenerationStats,
    CandidateSource,
    TokenCandidates,
    format_candidate_debug,
    format_document_debug,
    format_token_candidates_debug,
)
from vn_corrector.stage4_candidates.types import Candidate, CandidateEvidence


def _make_candidate(
    text: str,
    is_original: bool = False,
    edit_distance: int | None = None,
    replacement_token_count: int = 1,
) -> Candidate:
    return Candidate(
        text=text,
        normalized=text.lower(),
        no_tone_key=text.lower(),
        sources={CandidateSource.ORIGINAL if is_original else CandidateSource.SYLLABLE_MAP},
        evidence=[
            CandidateEvidence(
                source=CandidateSource.ORIGINAL if is_original else CandidateSource.SYLLABLE_MAP,
                detail="test evidence",
            )
        ],
        is_original=is_original,
        edit_distance=edit_distance,
        replacement_token_count=replacement_token_count,
    )


class TestFormatCandidateDebug:
    """Diagnostic output for a single candidate."""

    def test_basic_fields_present(self) -> None:
        c = _make_candidate("muỗng", is_original=False)
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "muỗng" in output
        assert "no_tone=" in output
        assert str(CandidateSource.SYLLABLE_MAP) in output
        assert "prior" in output
        assert "is_original" in output

    def test_original_marked(self) -> None:
        c = _make_candidate("test", is_original=True)
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "is_original=True" in output

    def test_edit_distance_included(self) -> None:
        c = _make_candidate("muỗng", edit_distance=1)
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "edit_distance=1" in output

    def test_replacement_token_count_included(self) -> None:
        c = _make_candidate("chung cư", replacement_token_count=2)
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "replacement_token_count=2" in output

    def test_replacement_token_count_one_omitted(self) -> None:
        """replacement_token_count of 1 is the default and should be omitted."""
        c = _make_candidate("test", replacement_token_count=1)
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "replacement_token_count" not in output

    def test_evidence_listed(self) -> None:
        ev = CandidateEvidence(
            source=CandidateSource.OCR_CONFUSION,
            detail="mùông -> muỗng",
        )
        c = Candidate(
            text="muỗng",
            normalized="muỗng",
            no_tone_key="muong",
            sources={CandidateSource.OCR_CONFUSION},
            evidence=[ev],
            is_original=False,
        )
        lines = format_candidate_debug(c)
        output = "\n".join(lines)
        assert "mùông -> muỗng" in output
        assert str(CandidateSource.OCR_CONFUSION) in output


class TestFormatTokenCandidatesDebug:
    """Diagnostic output for a token's candidates."""

    def test_basic_fields(self) -> None:
        tc = TokenCandidates(
            token_text="muỗng",
            token_index=0,
            protected=False,
            candidates=[_make_candidate("muỗng", is_original=True)],
        )
        lines = format_token_candidates_debug(tc)
        output = "\n".join(lines)
        assert "muỗng" in output
        assert "TokenCandidates" in output
        assert "idx=0" in output
        assert "protected=False" in output

    def test_candidate_count_shown(self) -> None:
        tc = TokenCandidates(
            token_text="test",
            token_index=0,
            protected=False,
            candidates=[
                _make_candidate("a", is_original=True),
                _make_candidate("b"),
            ],
        )
        lines = format_token_candidates_debug(tc)
        output = "\n".join(lines)
        assert "candidates (2)" in output

    def test_diagnostics_included(self) -> None:
        tc = TokenCandidates(
            token_text="test",
            token_index=0,
            protected=False,
            candidates=[_make_candidate("test", is_original=True)],
            diagnostics=["identity_only"],
        )
        lines = format_token_candidates_debug(tc)
        output = "\n".join(lines)
        assert "identity_only" in output
        assert "diag:" in output


class TestFormatDocumentDebug:
    """Diagnostic output for a full document."""

    def test_includes_stats(self) -> None:
        stats = CandidateGenerationStats(
            total_tokens=2,
            total_candidates=3,
        )
        doc = CandidateDocument(
            token_candidates=[
                TokenCandidates(
                    token_text="hello",
                    token_index=0,
                    protected=False,
                    candidates=[_make_candidate("hello", is_original=True)],
                ),
            ],
            stats=stats,
        )
        output = format_document_debug(doc)
        assert "CandidateDocument Debug" in output
        assert "total_tokens=2" in output
        assert "total_candidates=3" in output
        assert "hello" in output

    def test_empty_document(self) -> None:
        stats = CandidateGenerationStats()
        doc = CandidateDocument(token_candidates=[], stats=stats)
        output = format_document_debug(doc)
        assert "CandidateDocument Debug" in output


class TestDiagnosticsExported:
    """Diagnostics functions are exported from the package."""

    def test_format_candidate_debug_exported(self) -> None:
        from vn_corrector.stage4_candidates import format_candidate_debug as f

        assert callable(f)

    def test_format_token_candidates_debug_exported(self) -> None:
        from vn_corrector.stage4_candidates import format_token_candidates_debug as f

        assert callable(f)

    def test_format_document_debug_exported(self) -> None:
        from vn_corrector.stage4_candidates import format_document_debug as f

        assert callable(f)
