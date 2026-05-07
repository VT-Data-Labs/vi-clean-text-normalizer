from dataclasses import dataclass

from vn_corrector.common.constants import (
    AMBIGUOUS_MARGIN,
    MIN_MARGIN,
    REPLACE_THRESHOLD,
)


@dataclass(frozen=True, slots=True)
class DecisionEngineConfig:
    replace_threshold: float = REPLACE_THRESHOLD
    min_margin: float = MIN_MARGIN
    ambiguous_margin: float = AMBIGUOUS_MARGIN

    flag_low_confidence: bool = True
    flag_ambiguous: bool = True
    flag_need_context: bool = True
    flag_protected_change_attempts: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.replace_threshold <= 1.0:
            raise ValueError("replace_threshold must be between 0 and 1")
        if not 0.0 <= self.ambiguous_margin <= self.min_margin <= 1.0:
            raise ValueError("expected 0 <= ambiguous_margin <= min_margin <= 1")
