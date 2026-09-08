from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupmaxsize import GroupSizeLimiter


def limiter() -> GroupSizeLimiter:
    return GroupSizeLimiter(partition_count=4, standby_margin=2)


class TestJoining:
    def test_members_join_up_to_the_cap(self):
        limit = limiter()
        for number in range(6):
            limit.join(f"c{number}")
        assert len(limit.members) == 6

    def test_the_cap_is_partitions_plus_margin(self):
        assert limiter().cap() == 6

    def test_a_member_past_the_cap_is_refused(self):
        limit = limiter()
        for number in range(6):
            limit.join(f"c{number}")
        with pytest.raises(Invalid) as caught:
            limit.join("c6")
        assert "points at a leaking client" in str(caught.value)

    def test_rejoining_is_idempotent(self):
        limit = limiter()
        limit.join("c1")
        assert "already a member" in limit.join("c1")

    def test_bad_parameters_are_refused(self):
        with pytest.raises(Invalid):
            GroupSizeLimiter(partition_count=0, standby_margin=1)


class TestUtilization:
    def test_a_full_working_group_reads_healthy(self):
        limit = limiter()
        for number in range(4):
            limit.join(f"c{number}")
        util = limit.utilization()
        assert "4 working, 0 idle" in util

    def test_many_idle_members_signal_a_leak(self):
        limit = GroupSizeLimiter(partition_count=2, standby_margin=6)
        for number in range(6):
            limit.join(f"c{number}")
        util = limit.utilization()
        assert "2 working, 4 idle" in util
        assert "signal a leak" in util

    def test_leaving_frees_a_slot(self):
        limit = limiter()
        for number in range(6):
            limit.join(f"c{number}")
        limit.leave("c0")
        assert "joined" in limit.join("c6")
