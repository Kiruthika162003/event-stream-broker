from __future__ import annotations

import pytest

from relay.cogroup import CoGroup
from relay.errors import Invalid


def _cogroup():
    return CoGroup(
        aggregators={
            "orders": lambda acc, v: acc + v,
            "tickets": lambda acc, v: acc - v,
            "logins": lambda acc, _v: acc + 1,
        },
        partitions=4,
    )


class TestApply:
    def test_each_stream_folds_into_the_shared_state(self):
        cg = _cogroup()
        cg.apply("orders", "cust1", 100)
        cg.apply("tickets", "cust1", 30)
        assert cg.state["cust1"] == 70

    def test_logins_use_their_own_aggregator(self):
        cg = _cogroup()
        cg.apply("orders", "cust1", 50)
        cg.apply("logins", "cust1", 999)  # aggregator ignores value, adds 1
        assert cg.state["cust1"] == 51

    def test_an_unconfigured_stream_is_refused(self):
        cg = _cogroup()
        with pytest.raises(Invalid) as caught:
            cg.apply("unknown", "cust1", 1)
        assert "no aggregator" in str(caught.value)


class TestCoPartition:
    def test_a_partition_mismatch_is_refused(self):
        cg = _cogroup()
        with pytest.raises(Invalid):
            cg.require_copartitioned(8)


class TestCompleteness:
    def test_a_partially_contributed_key_is_incomplete(self):
        cg = _cogroup()
        cg.apply("orders", "cust1", 100)
        assert "1/3 stream(s)" in cg.completeness("cust1")

    def test_all_streams_make_it_complete(self):
        cg = _cogroup()
        cg.apply("orders", "cust1", 1)
        cg.apply("tickets", "cust1", 1)
        cg.apply("logins", "cust1", 1)
        assert "a complete value" in cg.completeness("cust1")


class TestConfig:
    def test_no_aggregators_is_refused(self):
        with pytest.raises(Invalid):
            CoGroup(aggregators={}, partitions=4)
