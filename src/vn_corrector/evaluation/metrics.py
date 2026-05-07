from __future__ import annotations


def edit_distance(a: str | list[str], b: str | list[str]) -> int:
    """Compute the Levenshtein edit distance between two sequences.

    Works on both strings and lists of strings (e.g. word sequences).
    """
    a_len = len(a)
    b_len = len(b)
    if a_len == 0:
        return b_len
    if b_len == 0:
        return a_len

    prev = list(range(b_len + 1))
    for i in range(1, a_len + 1):
        curr = [i] + [0] * b_len
        for j in range(1, b_len + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,
                prev[j] + 1,
                prev[j - 1] + cost,
            )
        prev = curr

    return prev[b_len]


def cer(predicted: str, expected: str) -> float:
    """Character error rate — edit_distance / len(expected)."""
    if not expected:
        return 0.0 if not predicted else 1.0
    return edit_distance(predicted, expected) / len(expected)


def wer(predicted: str, expected: str) -> float:
    """Word error rate — edit_distance(word_list) / len(expected_words)."""
    expected_words = expected.split()
    predicted_words = predicted.split()

    if not expected_words:
        return 0.0 if not predicted_words else 1.0

    return edit_distance(predicted_words, expected_words) / len(expected_words)
