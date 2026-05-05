"""Input validation helpers."""

from dataclasses import dataclass, field
from typing import Any

from vn_corrector.lexicon.accent_stripper import strip_accents


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
    """Validate a single syllable entry in grouped format (base/forms/freq).

    Checks:
    - Required fields: base, forms
    - All forms must strip back to base (strip_accents(form) == base)
    - No duplicate forms
    - If freq is provided, every form must have a frequency entry
    - All frequencies must be in [0, 1]
    """
    errors: list[str] = []
    base: str | None = None

    if "base" not in entry:
        errors.append("Missing required field 'base'")
    elif not is_nonempty_string(entry.get("base")):
        errors.append("'base' must be a non-empty string")
    else:
        base = str(entry["base"])

    if "forms" not in entry:
        errors.append("Missing required field 'forms'")
    elif not isinstance(entry.get("forms"), list) or len(entry["forms"]) == 0:
        errors.append("'forms' must be a non-empty list")
    elif base is not None:
        forms: list[str] = [str(f) for f in entry["forms"]]
        for form in forms:
            stripped = strip_accents(form)
            if stripped != base:
                errors.append(f"Form {form!r} strips to {stripped!r}, expected base {base!r}")

    if "freq" in entry and entry["freq"] is not None:
        freq = entry["freq"]
        if not isinstance(freq, dict):
            errors.append("'freq' must be a dict")
        else:
            for form, fval in freq.items():
                if not isinstance(fval, (int, float)) or not (0.0 <= fval <= 1.0):
                    errors.append(f"Frequency for '{form}' must be between 0 and 1, got {fval}")

    # If freq is provided, all forms must have a score
    if "freq" in entry and isinstance(entry.get("freq"), dict) and "forms" in entry:
        freq = entry["freq"]
        forms = entry["forms"]
        if isinstance(forms, list) and isinstance(freq, dict):
            for form in forms:
                fval = freq.get(str(form))
                if fval is None:
                    errors.append(f"Form {form!r} has no frequency score in 'freq' map")

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


def validate_phrase_entry(entry: dict[str, Any]) -> ValidationResult:
    """Validate a single phrase n-gram entry."""
    errors: list[str] = []

    for req_field in ("phrase", "normalized", "n"):
        if req_field not in entry:
            errors.append(f"Missing required field '{req_field}'")
        elif req_field == "phrase" and (
            not isinstance(entry.get("phrase"), str) or not entry["phrase"]
        ):
            errors.append("'phrase' must be a non-empty string")
        elif req_field == "normalized" and (
            not isinstance(entry.get("normalized"), str) or not entry["normalized"]
        ):
            errors.append("'normalized' must be a non-empty string")
        elif req_field == "n" and (not isinstance(entry.get("n"), int) or entry["n"] < 1):
            errors.append("'n' must be a positive integer")

    if "freq" in entry:
        freq = entry["freq"]
        if not isinstance(freq, (int, float)) or not (0.0 <= freq <= 1.0):
            errors.append(f"'freq' must be between 0 and 1, got {freq}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_ocr_confusion_entry(entry: dict[str, Any]) -> ValidationResult:
    """Validate a single OCR confusion entry."""
    errors: list[str] = []

    if "noisy" not in entry:
        errors.append("Missing required field 'noisy'")
    elif not isinstance(entry.get("noisy"), str) or not entry["noisy"]:
        errors.append("'noisy' must be a non-empty string")

    if "corrections" not in entry:
        errors.append("Missing required field 'corrections'")
    elif not isinstance(entry.get("corrections"), list):
        errors.append("'corrections' must be a list")
    elif len(entry["corrections"]) == 0:
        errors.append("'corrections' must be non-empty")
    else:
        for i, corr in enumerate(entry["corrections"]):
            if not isinstance(corr, str) or not corr.strip():
                errors.append(f"Correction at index {i} is empty")

    if "confidence" in entry:
        conf = entry["confidence"]
        if not isinstance(conf, (int, float)) or not (0.0 <= conf <= 1.0):
            errors.append(f"'confidence' must be between 0 and 1, got {conf}")

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
    elif lexicon_type == "phrase":
        validator = validate_phrase_entry
    elif lexicon_type == "ocr_confusion":
        validator = validate_ocr_confusion_entry
    else:
        return ValidationResult(valid=False, errors=[f"Unknown lexicon type: {lexicon_type}"])

    all_errors: list[str] = []

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            all_errors.append(f"Entry at index {i} must be a dict, got {type(entry).__name__}")
            continue

        result = validator(entry)
        for err in result.errors:
            all_errors.append(f"[{i}] {err}")

    return ValidationResult(valid=len(all_errors) == 0, errors=all_errors)
