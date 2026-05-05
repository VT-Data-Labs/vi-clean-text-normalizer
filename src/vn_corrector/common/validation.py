"""Input validation helpers."""


def is_nonempty_string(value: object) -> bool:
    """Check that value is a non-empty string."""
    return isinstance(value, str) and len(value) > 0


def is_probability(value: float) -> bool:
    """Check that value is in [0.0, 1.0]."""
    return isinstance(value, float) and 0.0 <= value <= 1.0
