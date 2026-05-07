from __future__ import annotations

import pytest

from vn_corrector.stage7_evaluation.metrics import cer, edit_distance, wer


class TestEditDistance:
    def test_empty_strings(self):
        assert edit_distance("", "") == 0
        assert edit_distance("", "abc") == 3
        assert edit_distance("abc", "") == 3

    def test_identical(self):
        assert edit_distance("hello", "hello") == 0

    def test_single_substitution(self):
        assert edit_distance("cat", "car") == 1

    def test_single_insertion(self):
        assert edit_distance("cat", "cast") == 1

    def test_single_deletion(self):
        assert edit_distance("cast", "cat") == 1

    def test_complex(self):
        assert edit_distance("kitten", "sitting") == 3

    def test_word_lists(self):
        a = ["tôi", "bán", "nhà"]
        b = ["tôi", "bán", "nhà"]
        assert edit_distance(a, b) == 0

    def test_word_lists_different(self):
        a = ["tôi", "bán", "nhà"]
        b = ["tôi", "bán", "nhà", "q7"]
        assert edit_distance(a, b) == 1

    def test_word_lists_substitution(self):
        a = ["toi", "ban", "nha"]
        b = ["tôi", "bán", "nhà"]
        assert edit_distance(a, b) == 3


class TestCer:
    def test_exact_match(self):
        assert cer("hello world", "hello world") == 0.0

    def test_empty_expected(self):
        assert cer("", "") == 0.0
        assert cer("a", "") == 1.0

    def test_single_char_error(self):
        c = cer("cat", "car")
        assert c == pytest.approx(1.0 / 3.0)

    def test_cer_bounded(self):
        c = cer("abc", "xyz")
        assert c == 1.0


class TestWer:
    def test_exact_match(self):
        assert wer("hello world", "hello world") == 0.0

    def test_empty_expected(self):
        assert wer("", "") == 0.0
        assert wer("hello", "") == 1.0

    def test_one_word_wrong(self):
        w = wer("tôi bán nhà", "tôi mua nhà")
        assert w == pytest.approx(1.0 / 3.0)

    def test_one_word_missing(self):
        w = wer("bán nhà", "tôi bán nhà")
        assert w == pytest.approx(1.0 / 3.0)

    def test_all_words_wrong(self):
        w = wer("toi ban nha", "tôi bán nhà")
        assert w == 1.0
