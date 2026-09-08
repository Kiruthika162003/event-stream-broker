from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.slowbroker import SlowBrokerDetector


class TestDetect:
    def test_a_broker_a_large_multiple_over_median_is_slow(self):
        d = SlowBrokerDetector(
            latencies={"b1": 10, "b2": 12, "b3": 11, "b4": 60},
        )
        assert d.slow_brokers() == ["b4"]

    def test_a_broker_just_above_median_is_not_slow(self):
        d = SlowBrokerDetector(latencies={"b1": 10, "b2": 12, "b3": 14})
        assert d.slow_brokers() == []

    def test_a_uniformly_slow_fleet_flags_no_one(self):
        d = SlowBrokerDetector(latencies={"b1": 100, "b2": 105, "b3": 110})
        assert d.slow_brokers() == []


class TestReport:
    def test_a_moderately_slow_broker_is_a_watch(self):
        d = SlowBrokerDetector(latencies={"b1": 10, "b2": 10, "b3": 40})
        note = d.report("b3")
        assert "4.0x the median" in note
        assert "watch" in note

    def test_a_very_slow_broker_is_a_remove(self):
        d = SlowBrokerDetector(latencies={"b1": 10, "b2": 10, "b3": 100})
        note = d.report("b3")
        assert "remove from the in-sync set" in note

    def test_a_healthy_broker_is_within_the_fleet(self):
        d = SlowBrokerDetector(latencies={"b1": 10, "b2": 12, "b3": 11})
        assert "within the fleet" in d.report("b1")


class TestConfig:
    def test_a_multiple_at_one_is_refused(self):
        with pytest.raises(Invalid):
            SlowBrokerDetector(latencies={"b1": 1}, multiple=1.0)
