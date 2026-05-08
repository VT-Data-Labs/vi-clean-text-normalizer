"""Configuration for Stage 4 — Candidate Generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CandidateGeneratorConfig:
    """Configuration for the candidate generator.

    Attributes control which sources are enabled, candidate limits,
    edit-distance guards, diagnostic output, and caching behaviour.
    """

    # -- Candidate limits --------------------------------------------------
    max_candidates_per_token: int = 32
    max_candidate_combinations_per_window: int = 5000
    max_tokens_per_combination_window: int = 7

    # -- Source toggles ----------------------------------------------------
    enable_original: bool = True
    enable_ocr_confusion: bool = True
    enable_syllable_map: bool = True
    enable_word_lexicon: bool = True
    enable_abbreviation: bool = True
    enable_phrase_evidence: bool = True
    enable_domain_specific: bool = True
    enable_edit_distance: bool = True

    # -- OCR confusion limits ----------------------------------------------
    max_ocr_replacements_per_token: int = 2
    max_phrase_window: int = 4

    # -- Edit-distance guards ----------------------------------------------
    max_edit_distance: int = 1
    min_token_length_for_edit_distance: int = 3
    max_token_length_for_edit_distance: int = 20

    # -- Token eligibility -------------------------------------------------
    skip_non_word_tokens: bool = True

    # -- Sorting / dedup ---------------------------------------------------
    keep_original_first: bool = True
    deterministic_sort: bool = True

    # -- Performance -------------------------------------------------------
    cache_enabled: bool = True
    enable_diagnostics: bool = False

    # -- Prior scoring weights (used for deterministic M4 ordering only) ---
    source_prior_weights: dict[str, float] = field(
        default_factory=lambda: {
            "original": 0.10,
            "phrase_specific": 0.35,
            "ocr_confusion": 0.30,
            "word_lexicon": 0.25,
            "syllable_map": 0.20,
            "abbreviation": 0.15,
            "domain_specific": 0.20,
            "edit_distance": 0.05,
        }
    )

    # -- Token types that should produce identity-only candidates ----------
    identity_token_types: tuple[str, ...] = (
        "NUMBER",
        "UNIT",
        "PUNCT",
        "SPACE",
        "NEWLINE",
        "PROTECTED",
    )

    # -- Eligible token types for full candidate generation ----------------
    candidate_token_types: tuple[str, ...] = (
        "VI_WORD",
        "UNKNOWN",
        "FOREIGN_WORD",
    )


__all__ = ["CandidateGeneratorConfig"]
