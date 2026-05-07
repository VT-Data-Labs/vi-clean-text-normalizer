"""Pipeline orchestrator — :class:`TextCorrector` and :func:`correct_text`."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from vn_corrector.common.correction import CorrectionChange, CorrectionFlag, CorrectionResult
from vn_corrector.common.enums import FlagType
from vn_corrector.common.spans import ProtectedSpan, TextSpan, Token
from vn_corrector.pipeline.config import PipelineConfig
from vn_corrector.pipeline.context import PipelineContext, build_pipeline_context
from vn_corrector.pipeline.errors import PipelineInputTooLargeError
from vn_corrector.pipeline.reconstruction import apply_changes, resolve_overlapping_changes
from vn_corrector.stage4_candidates import CandidateGenerator
from vn_corrector.stage5_scorer import PhraseScorer
from vn_corrector.stage5_scorer.windowing import build_windows
from vn_corrector.stage6_decision import DecisionEngine, decide_scored_window


def _is_token_protected(token: Token, protected_spans: Sequence[ProtectedSpan]) -> bool:
    return any(ps.start <= token.span.start and token.span.end <= ps.end for ps in protected_spans)


def _mark_protected_tokens(
    tokens: list[Token],
    protected_spans: Sequence[ProtectedSpan],
) -> list[Token]:
    if not protected_spans:
        return tokens
    result: list[Token] = []
    for t in tokens:
        if _is_token_protected(t, protected_spans) and not t.protected:
            result.append(
                Token(
                    text=t.text,
                    token_type=t.token_type,
                    span=t.span,
                    normalized=t.normalized,
                    no_tone=t.no_tone,
                    protected=True,
                    metadata=t.metadata,
                )
            )
        else:
            result.append(t)
    return result


def _fix_span_to_character_offsets(
    change: CorrectionChange,
    token_index: int,
    tokens: list[Token],
) -> CorrectionChange:
    """Replace index-based ``TextSpan`` with actual character offsets."""
    if 0 <= token_index < len(tokens):
        token = tokens[token_index]
        char_span = TextSpan(start=token.span.start, end=token.span.end)
        if char_span != change.span:
            return CorrectionChange(
                original=change.original,
                replacement=change.replacement,
                span=char_span,
                confidence=change.confidence,
                reason=change.reason,
                decision=change.decision,
                candidate_sources=change.candidate_sources,
            )
    return change


class TextCorrector:
    """Reusable correction pipeline.

    Loads dependencies once and reuses them across many ``correct()``
    calls.  Use :func:`correct_text` for one-off convenience.
    """

    def __init__(
        self,
        config: PipelineConfig | None = None,
        lexicon: Any | None = None,
        candidate_generator: CandidateGenerator | None = None,
        scorer: PhraseScorer | None = None,
        decision_engine: DecisionEngine | None = None,
    ) -> None:
        self._config = config or PipelineConfig()
        self._context: PipelineContext | None = None

        if any(x is not None for x in (lexicon, candidate_generator, scorer, decision_engine)):
            ctx = self._build_partial_context(lexicon, candidate_generator, scorer, decision_engine)
            self._context = ctx
        else:
            self._context = build_pipeline_context(self._config)

    def _build_partial_context(
        self,
        lexicon: Any | None,
        candidate_generator: CandidateGenerator | None,
        scorer: PhraseScorer | None,
        decision_engine: DecisionEngine | None,
    ) -> PipelineContext:
        from vn_corrector.pipeline.context import (
            _build_decision_config,
        )

        ctx = build_pipeline_context(self._config)
        if lexicon is not None:
            ctx.lexicon = lexicon
        if candidate_generator is not None:
            ctx.candidate_generator = candidate_generator
        if scorer is not None:
            ctx.scorer = scorer
        if decision_engine is not None:
            ctx.decision_engine = decision_engine

        if (
            candidate_generator is not None
            and lexicon is None
            and hasattr(candidate_generator, "_lexicon")
        ):
            ctx.lexicon = candidate_generator._lexicon

        if scorer is not None and lexicon is None and hasattr(scorer, "_lexicon"):
            ctx.lexicon = scorer._lexicon

        ctx.decision_engine_config = _build_decision_config(self._config)
        return ctx

    def correct(
        self,
        text: str,
        domain: str | None = None,
    ) -> CorrectionResult:
        """Run the full correction pipeline on *text*."""
        ctx = self._context
        if ctx is None:
            ctx = build_pipeline_context(self._config)
            self._context = ctx

        # Input validation (not caught by fail_closed)
        if not isinstance(text, str):
            raise TypeError("text must be str")

        max_chars = ctx.config.max_input_chars
        if len(text) > max_chars:
            raise PipelineInputTooLargeError(
                f"Input exceeds max_input_chars={max_chars} (got {len(text)} characters)"
            )

        try:
            return self._run_pipeline(text, domain, ctx)
        except Exception:
            if self._config.fail_closed:
                return CorrectionResult(
                    original_text=text,
                    corrected_text=text,
                    confidence=0.0,
                    flags=(
                        CorrectionFlag(
                            span_text=text[:50],
                            span=TextSpan(start=0, end=len(text)),
                            flag_type=FlagType.NO_SAFE_CORRECTION,
                            reason="pipeline execution error, returned original text",
                        ),
                    ),
                    metadata={"pipeline_status": "fail_closed"},
                )
            raise

    def _run_pipeline(
        self,
        text: str,
        domain: str | None,
        ctx: PipelineContext,
    ) -> CorrectionResult:
        # --- Step 1: Validate empty ---
        if text == "":
            return CorrectionResult(
                original_text=text,
                corrected_text=text,
                confidence=1.0,
            )

        # --- Step 2: Normalize (conservative -- no lowercase) ---
        normalized = text
        if ctx.config.normalize:
            from vn_corrector.normalizer import normalize

            normalized = normalize(text)

        # --- Step 3: Detect protected spans ---
        protected_spans: Sequence[ProtectedSpan] = ()
        if ctx.config.protect_tokens:
            from vn_corrector.protected_tokens import protect

            try:
                doc = protect(normalized)
                protected_spans = doc.spans
            except Exception:
                protected_spans = ()

        # --- Step 4: Tokenize ---
        from vn_corrector.tokenizer import tokenize

        tokens = tokenize(normalized)

        # Mark tokens that overlap protected spans
        tokens = _mark_protected_tokens(tokens, protected_spans)

        # --- Step 5: Generate candidates ---
        cand_doc = ctx.candidate_generator.generate_document(tokens, protected_spans)

        # --- Step 6: Build windows ---
        windows = build_windows(
            cand_doc.token_candidates,
            max_tokens_per_window=ctx.config.max_window_size,
        )

        # --- Step 7-8: Score windows and decide ---
        all_changes: list[CorrectionChange] = []
        all_flags: list[CorrectionFlag] = []

        for window in windows:
            scored = ctx.scorer.score_window(window, domain)

            _unused_decisions, changes, flags = decide_scored_window(
                scored,
                config=ctx.decision_engine_config,
            )

            for change in changes:
                token_idx = change.span.start
                fixed = _fix_span_to_character_offsets(change, token_idx, tokens)
                all_changes.append(fixed)

            for flag in flags:
                token_idx = flag.span.start
                if 0 <= token_idx < len(tokens):
                    t = tokens[token_idx]
                    char_span = TextSpan(start=t.span.start, end=t.span.end)
                    if flag.span != char_span:
                        flag = CorrectionFlag(
                            span_text=flag.span_text,
                            span=char_span,
                            flag_type=flag.flag_type,
                            candidates=flag.candidates,
                            reason=flag.reason,
                            severity=flag.severity,
                        )
                all_flags.append(flag)

        # --- Step 9: Resolve overlapping changes ---
        accepted = resolve_overlapping_changes(all_changes)

        # --- Step 10: Reconstruct ---
        corrected = apply_changes(normalized, accepted)

        # --- Step 11: Compute overall confidence ---
        if not accepted:
            overall_confidence = 1.0
        else:
            overall_confidence = sum(c.confidence for c in accepted) / len(accepted)

        # --- Step 12: Build result ---
        return CorrectionResult(
            original_text=text,
            corrected_text=corrected,
            confidence=overall_confidence,
            changes=tuple(accepted),
            flags=tuple(all_flags),
            metadata={
                "pipeline_version": "m6.5",
                "normalized_text": normalized,
                "num_tokens": len(tokens),
                "num_candidates": cand_doc.stats.total_candidates if cand_doc.stats else 0,
                "num_windows": len(windows),
                "num_accepted": len(accepted),
                "num_flags": len(all_flags),
            },
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

_DEFAULT_CORRECTOR: TextCorrector | None = None


@lru_cache(maxsize=1)
def _get_default_corrector() -> TextCorrector:
    return TextCorrector()


def correct_text(
    text: str,
    domain: str | None = None,
    *,
    config: PipelineConfig | None = None,
    corrector: TextCorrector | None = None,
) -> CorrectionResult:
    """Correct Vietnamese text through the full pipeline.

    Parameters
    ----------
    text:
        Input text to correct.
    domain:
        Optional domain context (e.g. ``"milk_instruction"``).
    config:
        Override pipeline configuration.  Ignored when *corrector* is
        provided.
    corrector:
        Reusable :class:`TextCorrector` instance.  When omitted, a
        module-level cached default is used.

    Returns
    -------
    CorrectionResult
        The correction output with changes, flags, and metadata.
    """
    if corrector is not None:
        return corrector.correct(text, domain)

    if config is not None:
        return TextCorrector(config=config).correct(text, domain)

    return _get_default_corrector().correct(text, domain)
