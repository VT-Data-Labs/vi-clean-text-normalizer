"""
Stage 2 + Stage 8: Case Masking and Restoration.

Responsibilities:
- Detect case pattern for each text span (UPPER, LOWER, TITLE, MIXED, UNKNOWN).
- Produce a lowercase working copy for internal processing.
- Record enough metadata to restore original casing after correction.
- Handle Vietnamese uppercase/lowercase correctly, including Đ/đ.
"""

from vn_corrector.common.types import CaseMask, CasePattern

# Vietnamese uppercase/lowercase is handled by Python's str.upper()/str.lower()
# which correctly maps:
#   đ → Đ, Đ → đ
#   All tone-marked vowels: à → À, Ạ → ạ, etc.


def detect_case_pattern(text: str) -> CasePattern:
    """Detect the case pattern of a text span.

    Detection rules:
    - Empty or no alphabetic characters → UNKNOWN
    - All alphabetic characters are uppercase → UPPER
    - All alphabetic characters are lowercase → LOWER
    - First letter uppercase, rest lowercase → TITLE
    - Mixed uppercase and lowercase → MIXED
    """
    alpha_chars = [ch for ch in text if ch.isalpha()]

    if not alpha_chars:
        return CasePattern.UNKNOWN

    has_upper = any(ch.isupper() for ch in alpha_chars)
    has_lower = any(ch.islower() for ch in alpha_chars)

    if has_upper and has_lower:
        # Could be TITLE or MIXED
        if alpha_chars[0].isupper() and all(ch.islower() for ch in alpha_chars[1:]):
            return CasePattern.TITLE
        return CasePattern.MIXED

    if has_upper:
        return CasePattern.UPPER

    if has_lower:
        return CasePattern.LOWER

    return CasePattern.UNKNOWN


def to_lowercase(text: str) -> str:
    """Convert text to lowercase, correctly handling Vietnamese.

    Correctly maps:
    - Đ → đ, đ → đ
    - RỐT → rốt, SỐ → số
    - English text works as expected
    """
    return text.lower()


def to_uppercase(text: str) -> str:
    """Convert text to uppercase, correctly handling Vietnamese.

    Correctly maps:
    - đ → Đ, Đ → Đ
    - rốt → RỐT, số → SỐ
    """
    return text.upper()


def restore_case(text: str, case_pattern: CasePattern, original: str | None = None) -> str:
    """Restore the case pattern onto *text*.

    Args:
        text: The working (corrected) text to apply case to.
        case_pattern: The target case pattern.
        original: The original text (required for MIXED restoration).

    Returns:
        Text with the requested case pattern applied.
    """
    if case_pattern == CasePattern.LOWER:
        return to_lowercase(text)

    if case_pattern == CasePattern.UPPER:
        return to_uppercase(text)

    if case_pattern == CasePattern.TITLE:
        return _to_title_case(text)

    if case_pattern == CasePattern.MIXED:
        if original is not None:
            return _apply_mixed_case(original, text)
        # Fallback: preserve text as-is
        return text

    return text


def create_case_mask(text: str) -> CaseMask:
    """Create a CaseMask by detecting case pattern and producing the working copy.

    Args:
        text: The original text span.

    Returns:
        A CaseMask with original, lowercase working copy, and detected pattern.
    """
    case_pattern = detect_case_pattern(text)
    working = to_lowercase(text)
    return CaseMask(
        original=text,
        working=working,
        case_pattern=case_pattern,
    )


def apply_case_mask(working_text: str, mask: CaseMask) -> str:
    """Restore case from a CaseMask onto the given working text.

    Args:
        working_text: The corrected/lowercase text.
        mask: The CaseMask with original pattern metadata.

    Returns:
        Text with original case pattern restored.
    """
    return restore_case(working_text, mask.case_pattern, mask.original)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_title_case(text: str) -> str:
    """Convert text to title case (first letter uppercase, rest lowercase).

    Handles empty strings and single-character strings.
    """
    if not text:
        return text
    if len(text) == 1:
        return text.upper()
    return text[0].upper() + text[1:].lower()


def _apply_mixed_case(original: str, working: str) -> str:
    """Apply the mixed-case pattern from *original* onto *working*.

    For each character position, if the original character was uppercase,
    the corresponding working character is uppercased; otherwise it's lowercased.
    If lengths differ, remaining characters are lowercased.
    """
    result_parts = []
    for i, w_ch in enumerate(working):
        if i < len(original):
            if original[i].isupper():
                result_parts.append(w_ch.upper())
            else:
                result_parts.append(w_ch.lower())
        else:
            # Working text longer than original — lowercase remaining
            result_parts.append(w_ch.lower())
    return "".join(result_parts)
