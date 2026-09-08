from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rebalancestorm import StormDetector


class TestStorm:
    def test_rebalances_over_the_threshold_are_a_storm(self):
        d = StormDetector(window=1000, threshold=3)
        d.record_rebalance(100, "m1")
        d.record_rebalance(200, "m1")
        d.record_rebalance(300, "m1")
        assert d.is_storm()

    def test_old_rebalances_fall_out_of_the_window(self):
        d = StormDetector(window=100, threshold=3)
        d.record_rebalance(0, "m1")
        d.record_rebalance(10, "m1")
        d.record_rebalance(500, "m1")
        assert not d.is_storm()

    def test_a_zero_window_is_refused(self):
        with pytest.raises(Invalid):
            StormDetector(window=0, threshold=1)


class TestChurnLeader:
    def test_the_flapping_member_is_named(self):
        d = StormDetector(window=1000, threshold=2)
        d.record_rebalance(100, "flaky")
        d.record_rebalance(200, "flaky")
        d.record_rebalance(300, "steady")
        assert d.churn_leader() == "flaky"


class TestQuarantine:
    def test_a_flapper_past_the_limit_can_be_quarantined(self):
        d = StormDetector(window=1000, threshold=2, stable_members=3)
        for _ in range(3):
            d.record_rebalance(100, "flaky")
        note = d.may_quarantine("flaky", flap_limit=3)
        assert "quarantine flaky" in note

    def test_the_last_stable_member_is_not_quarantined(self):
        d = StormDetector(window=1000, threshold=2, stable_members=1)
        for _ in range(5):
            d.record_rebalance(100, "flaky")
        with pytest.raises(Invalid) as caught:
            d.may_quarantine("flaky", flap_limit=3)
        assert "empty group consumes nothing" in str(caught.value)

    def test_a_member_under_the_limit_is_not_the_culprit(self):
        d = StormDetector(window=1000, threshold=2, stable_members=3)
        d.record_rebalance(100, "flaky")
        with pytest.raises(Invalid) as caught:
            d.may_quarantine("flaky", flap_limit=3)
        assert "not yet the culprit" in str(caught.value)


class TestReport:
    def test_report_names_verdict_and_leader(self):
        d = StormDetector(window=1000, threshold=2)
        d.record_rebalance(100, "flaky")
        d.record_rebalance(200, "flaky")
        note = d.report()
        assert "STORM" in note
        assert "churn leader 'flaky'" in note
