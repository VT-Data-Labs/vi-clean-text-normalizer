"""Configuration for the normalization pipeline."""

from dataclasses import dataclass, field


@dataclass
class NormalizerConfig:
    """Controls which normalization steps are enabled.

    All steps are enabled by default. Disabling a step skips it
    entirely in the pipeline.
    """

    normalize_unicode: bool = True
    remove_invisible: bool = True
    normalize_whitespace: bool = True

    # Future-proofing hooks — these will be used in later milestones.
    detect_language: bool = False
    ocr_confidence_aware: bool = False
    markdown_aware: bool = False
    extra_steps: list[str] = field(default_factory=list)
