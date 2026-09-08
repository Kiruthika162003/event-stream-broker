from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.weightedassign import assign, spread


class TestAssign:
    def test_equal_weights_split_evenly(self):
        result = assign(6, {"a": 1, "b": 1, "c": 1})
        assert result == {"a": 2, "b": 2, "c": 2}

    def test_a_double_weight_gets_roughly_double(self):
        result = assign(9, {"big": 2, "small": 1})
        assert result == {"big": 6, "small": 3}

    def test_every_partition_is_assigned_exactly_once(self):
        result = assign(10, {"a": 3, "b": 2, "c": 1})
        assert sum(result.values()) == 10

    def test_the_remainder_goes_to_the_largest_fraction(self):
        # ideals: a=2.5, b=2.5 -> floors 2,2, one leftover to the
        # first by remainder tie-break; total stays 5.
        result = assign(5, {"a": 1, "b": 1})
        assert sum(result.values()) == 5
        assert set(result.values()) == {2, 3}

    def test_a_zero_weight_consumer_is_refused(self):
        with pytest.raises(Invalid) as caught:
            assign(6, {"a": 1, "b": 0})
        assert "positive weight" in str(caught.value)

    def test_no_consumers_is_refused(self):
        with pytest.raises(Invalid):
            assign(6, {})


class TestSpread:
    def test_the_spread_is_reported(self):
        note = spread(9, {"big": 2, "small": 1})
        assert "load-per-weight spread" in note
        assert "matches partitions to capacity" in note
