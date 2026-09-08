from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.quotas import ClientQuota


def quota() -> ClientQuota:
    return ClientQuota(
        client_id="c1", bytes_per_tick=100, window_ticks=10
    )


class TestThrottling:
    def test_traffic_under_budget_is_not_throttled(self):
        verdict = quota().record(now=1, size=500)
        assert "no throttle" in verdict

    def test_over_budget_delays_by_the_computed_amount(self):
        chosen = quota()
        chosen.record(now=1, size=500)
        verdict = chosen.record(now=2, size=800)
        assert "300 bytes over, delayed 3 tick(s)" in verdict
        assert "not disconnected" in verdict

    def test_the_window_forgives_an_old_burst(self):
        chosen = quota()
        chosen.record(now=1, size=1000)
        verdict = chosen.record(now=20, size=100)
        assert "no throttle" in verdict

    def test_a_bad_quota_is_refused(self):
        with pytest.raises(Invalid):
            ClientQuota("c", bytes_per_tick=0, window_ticks=10)
        with pytest.raises(Invalid):
            ClientQuota("c", bytes_per_tick=10, window_ticks=0)


class TestTheBill:
    def test_the_bill_totals_the_throttle_and_names_the_reason(self):
        chosen = quota()
        chosen.record(now=1, size=500)
        chosen.record(now=2, size=800)
        bill = chosen.bill()
        assert "3 throttle tick(s) applied" in bill
        assert "retries harder" in bill
