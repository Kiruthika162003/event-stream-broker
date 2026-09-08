from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.slidingmax import SlidingMax


class TestMaximum:
    def test_the_maximum_over_the_window(self):
        s = SlidingMax(window=3)
        for v in (1, 3, 2):
            s.push(v)
        assert s.maximum() == 3

    def test_the_max_slides_out_of_the_window(self):
        s = SlidingMax(window=3)
        for v in (5, 1, 2, 3):
            s.push(v)
        # 5 has slid out; window is [1,2,3]
        assert s.maximum() == 3

    def test_a_new_peak_dominates(self):
        s = SlidingMax(window=3)
        for v in (1, 2, 9):
            s.push(v)
        assert s.maximum() == 9

    def test_an_empty_window_has_no_maximum(self):
        s = SlidingMax(window=3)
        with pytest.raises(Invalid):
            s.maximum()


class TestKnownSequence:
    def test_matches_a_brute_force_sliding_max(self):
        values = [4, 2, 12, 3, 8, 1, 7, 9, 5]
        window = 3
        s = SlidingMax(window=window)
        got = []
        for i, v in enumerate(values):
            s.push(v)
            if i >= window - 1:
                got.append(s.maximum())
        expected = [
            max(values[i - window + 1:i + 1])
            for i in range(window - 1, len(values))
        ]
        assert got == expected


class TestConfig:
    def test_a_zero_window_is_refused(self):
        with pytest.raises(Invalid):
            SlidingMax(window=0)

    def test_report_names_the_deque_size(self):
        s = SlidingMax(window=5)
        s.push(1)
        assert "deque holds" in s.report()
