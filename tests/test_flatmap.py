from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.flatmap import FlatMap


class TestApply:
    def test_one_record_expands_to_many(self):
        fm = FlatMap(fan_out=lambda n: [n] * n)
        assert fm.apply(3) == [3, 3, 3]

    def test_a_record_can_expand_to_none(self):
        fm = FlatMap(fan_out=lambda n: [] if n < 0 else [n])
        assert fm.apply(-1) == []

    def test_a_non_list_return_is_refused(self):
        fm = FlatMap(fan_out=lambda n: n)  # returns a bare int
        with pytest.raises(Invalid) as caught:
            fm.apply(5)
        assert "must return a list" in str(caught.value)


class TestRatio:
    def test_an_amplifier_ratio_exceeds_one(self):
        fm = FlatMap(fan_out=lambda n: [n, n, n])
        fm.apply_all([1, 2, 3])
        assert fm.fan_out_ratio() == 3.0
        assert "an amplifier" in fm.report()

    def test_a_filter_ratio_is_below_one(self):
        fm = FlatMap(fan_out=lambda n: [n] if n % 2 == 0 else [])
        fm.apply_all([1, 2, 3, 4])
        assert fm.fan_out_ratio() == 0.5
        assert "a filter" in fm.report()

    def test_a_one_to_one_ratio(self):
        fm = FlatMap(fan_out=lambda n: [n])
        fm.apply_all([1, 2])
        assert "one-to-one" in fm.report()
