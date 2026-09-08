from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.offsetexpiry import GroupOffset, OffsetExpirer


def offsets() -> list[GroupOffset]:
    return [
        GroupOffset("live", 0, committed_offset=100, last_commit_tick=1000),
        GroupOffset("idle-live", 0, committed_offset=50, last_commit_tick=0),
        GroupOffset("gone", 0, committed_offset=10, last_commit_tick=0),
    ]


class TestExpiry:
    def test_a_stale_gone_group_expires(self):
        expirer = OffsetExpirer(retention_ticks=100)
        survivors = expirer.sweep(
            offsets(), active_groups={"live", "idle-live"}, now=1000
        )
        names = {s.group for s in survivors}
        assert "gone" not in names
        assert expirer.expired == 1

    def test_an_idle_but_live_group_is_protected(self):
        expirer = OffsetExpirer(retention_ticks=100)
        survivors = expirer.sweep(
            offsets(), active_groups={"live", "idle-live"}, now=1000
        )
        names = {s.group for s in survivors}
        assert "idle-live" in names
        assert expirer.protected_active == 2

    def test_a_recent_commit_survives_even_if_inactive(self):
        expirer = OffsetExpirer(retention_ticks=100)
        recent = [
            GroupOffset("recent", 0, committed_offset=5, last_commit_tick=950)
        ]
        survivors = expirer.sweep(recent, active_groups=set(), now=1000)
        assert len(survivors) == 1

    def test_a_bad_retention_is_refused(self):
        with pytest.raises(Invalid):
            OffsetExpirer(retention_ticks=0)


class TestTheReport:
    def test_the_report_names_the_healthy_nonzero(self):
        expirer = OffsetExpirer(retention_ticks=100)
        expirer.sweep(offsets(), active_groups={"live"}, now=1000)
        report = expirer.report()
        assert "expired freeing" in report
        assert "healthy is a small nonzero" in report

    def test_an_unswept_expirer_says_so(self):
        assert OffsetExpirer(retention_ticks=100).report() == (
            "nothing swept yet"
        )
