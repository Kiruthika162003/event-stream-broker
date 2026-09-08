from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.staticmembership import StaticGroup


def group() -> StaticGroup:
    built = StaticGroup(session_timeout=30)
    built.join("consumer-a", {0, 1}, now=0)
    return built


class TestReclaiming:
    def test_a_quick_restart_reclaims_without_rebalance(self):
        chosen = group()
        chosen.disconnect("consumer-a", now=10)
        verdict = chosen.reconnect("consumer-a", now=20)
        assert "reclaimed [0, 1] with no rebalance" in verdict
        assert chosen.rebalances_avoided == 1

    def test_a_long_absence_forces_reassignment(self):
        chosen = group()
        chosen.disconnect("consumer-a", now=10)
        with pytest.raises(Invalid) as caught:
            chosen.reconnect("consumer-a", now=100)
        assert "the double-ownership we prevent" in str(
            caught.value
        )
        assert chosen.rebalances_forced == 1

    def test_a_new_instance_id_has_no_static_identity(self):
        with pytest.raises(Invalid) as caught:
            group().reconnect("consumer-z", now=5)
        assert "must be assigned" in str(caught.value)


class TestRefusals:
    def test_a_bad_timeout_is_refused(self):
        with pytest.raises(Invalid):
            StaticGroup(session_timeout=0)

    def test_disconnecting_a_stranger_is_refused(self):
        with pytest.raises(Invalid):
            group().disconnect("ghost", now=5)


class TestTheReport:
    def test_the_report_names_the_deploy_time_value(self):
        chosen = group()
        chosen.disconnect("consumer-a", now=5)
        chosen.reconnect("consumer-a", now=10)
        report = chosen.report()
        assert "1 rebalance(s) avoided" in report
        assert "only shows up during a deploy" in report
