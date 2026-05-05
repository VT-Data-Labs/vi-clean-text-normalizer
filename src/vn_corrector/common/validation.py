"""Input validation helpers."""

from dataclasses import dataclass, field
from typing import Any


def is_nonempty_string(value: object) -> bool:
    """Check that value is a non-empty string."""
    return isinstance(value, str) and len(value) > 0


def is_probability(value: object) -> bool:
    """Check that value is in [0.0, 1.0]."""
    return isinstance(value, float) and 0.0 <= value <= 1.0


@dataclass
class ValidationResult:
    """Result of a lexicon JSON validation pass."""

    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_syllable_entry(entry: dict[str, Any]) -> ValidationResult:
    """Validate a single syllable entry in grouped format (base/forms/freq)."""
    errors: list[str] = []

    if "base" not in entry:
        errors.append("Missing required field 'base'")
    elif not is_nonempty_string(entry.get("base")):
        errors.append("'base' must be a non-empty string")

    if "forms" not in entry:
        errors.append("Missing required field 'forms'")
    elif not isinstance(entry.get("forms"), list) or len(entry["forms"]) == 0:
        errors.append("'forms' must be a non-empty list")

    if "freq" in entry and entry["freq"] is not None:
        freq = entry["freq"]
        if not isinstance(freq, dict):
            errors.append("'freq' must be a dict")
        else:
            for form, fval in freq.items():
                if not isinstance(fval, (int, float)) or not (0.0 <= fval <= 1.0):
                    errors.append(f"Frequency for '{form}' must be between 0 and 1, got {fval}")

    if "forms" in entry and isinstance(entry.get("forms"), list):
        seen = set()
        for form in entry["forms"]:
            if form in seen:
                errors.append(f"Duplicate form '{form}' in same entry")
            seen.add(form)

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_word_entry(entry: dict[str, Any]) -> ValidationResult:
    """Validate a single word/unit lexicon entry."""
    errors: list[str] = []

    for req_field in ("surface", "normalized"):
        if req_field not in entry:
            errors.append(f"Missing required field '{req_field}'")
        elif not is_nonempty_string(entry.get(req_field)):
            errors.append(f"'{req_field}' must be a non-empty string")

    if "freq" in entry:
        freq = entry["freq"]
        if not isinstance(freq, (int, float)) or not (0.0 <= freq <= 1.0):
            errors.append(f"'freq' must be between 0 and 1, got {freq}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_abbreviation_entry(entry: dict[str, Any]) -> ValidationResult:
    """Validate a single abbreviation entry."""
    errors: list[str] = []

    if "abbreviation" not in entry:
        errors.append("Missing required field 'abbreviation'")
    elif not is_nonempty_string(entry.get("abbreviation")):
        errors.append("'abbreviation' must be a non-empty string")

    if "expansions" not in entry:
        errors.append("Missing required field 'expansions'")
    elif not isinstance(entry.get("expansions"), list):
        errors.append("'expansions' must be a list")
    elif len(entry["expansions"]) == 0:
        errors.append("'expansions' must be non-empty")
    else:
        for i, exp in enumerate(entry["expansions"]):
            if not is_nonempty_string(exp):
                errors.append(f"Expansion at index {i} is empty")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_lexicon_file(data: list[Any] | dict[str, Any], lexicon_type: str) -> ValidationResult:
    """Validate an entire lexicon JSON file.

    Args:
        data: Parsed JSON data (list of entries, or list of strings for foreign_words).
        lexicon_type: One of 'syllable', 'word', 'unit', 'abbreviation', 'foreign_words'.

    Returns:
        A ValidationResult with any errors found.
    """
    if not isinstance(data, list):
        return ValidationResult(valid=False, errors=["Lexicon data must be a list"])

    if lexicon_type == "foreign_words":
        for i, item in enumerate(data):
            if not isinstance(item, str) or not item.strip():
                return ValidationResult(
                    valid=False,
                    errors=[f"Index {i}: expected non-empty string, got {type(item).__name__}"],
                )
        return ValidationResult(valid=True)

    if lexicon_type == "syllable":
        validator = validate_syllable_entry
    elif lexicon_type in ("word", "unit"):
        validator = validate_word_entry
    elif lexicon_type == "abbreviation":
        validator = validate_abbreviation_entry
    else:
        return ValidationResult(valid=False, errors=[f"Unknown lexicon type: {lexicon_type}"])

    all_errors: list[str] = []
    seen_normalized: dict[str, int] = {}

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            all_errors.append(f"Entry at index {i} must be a dict, got {type(entry).__name__}")
            continue

        result = validator(entry)
        for err in result.errors:
            all_errors.append(f"[{i}] {err}")

        # Check for duplicate normalized entries (unless explicitly allowed)
        if lexicon_type in ("word", "unit"):
            normalized = entry.get("normalized")
            if normalized and isinstance(normalized, str):
                if normalized in seen_normalized:
                    prev_idx = seen_normalized[normalized]
                    all_errors.append(
                        f"[{i}] Duplicate normalized '{normalized}' (also at index {prev_idx})"
                    )
                else:
                    seen_normalized[normalized] = i

    return ValidationResult(valid=len(all_errors) == 0, errors=all_errors)
