"""Configuration for the M5 phrase scorer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseScorerConfig:
    """Configuration for the phrase-level candidate scorer."""

    max_tokens_per_window: int = 7
    max_combinations: int = 5000
    max_candidates_per_token: int = 8
    min_score_margin: float = 0.25
    min_apply_confidence: float = 0.65
    enable_bigram_score: bool = True
    enable_trigram_score: bool = True
    enable_fourgram_score: bool = True
    enable_domain_context: bool = True
    enable_negative_phrase_penalty: bool = True

    # Beam search (production path)
    enable_beam_search: bool = True
    beam_size: int = 32
    beam_candidates_per_token: int = 8
