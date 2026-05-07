from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for the correction pipeline.

    Parameters
    ----------
    normalize:
        Run Unicode and whitespace normalization before correction.
    protect_tokens:
        Detect and protect spans (URLs, phones, numbers, etc.).
    enable_case_masking:
        Mask uppercase input to lowercase before correction, then restore
        original case in the output.
    max_candidates_per_token:
        Maximum candidates to consider per token.
    max_window_size:
        Maximum tokens per scoring window.
    min_accept_confidence:
        Minimum confidence to accept a correction (maps to
        ``replace_threshold`` in the decision engine).
    min_margin:
        Minimum score margin over the second-best candidate.
    preserve_unknown_tokens:
        Never change tokens the system cannot identify.
    enable_phrase_scoring:
        Enable n-gram phrase-level scoring.
    enable_diagnostics:
        Collect and expose debug/diagnostic information.
    fail_closed:
        If ``True``, return original text on unexpected errors
        instead of raising.
    max_input_chars:
        Maximum input length.  Raises
        :class:`PipelineInputTooLargeError` when exceeded.
    """

    normalize: bool = True
    protect_tokens: bool = True
    enable_case_masking: bool = True
    max_candidates_per_token: int = 8
    max_window_size: int = 5
    min_accept_confidence: float = 0.72
    min_margin: float = 0.08
    preserve_unknown_tokens: bool = True
    enable_phrase_scoring: bool = True
    enable_diagnostics: bool = False
    fail_closed: bool = True
    max_input_chars: int = 20_000
