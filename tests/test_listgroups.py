from __future__ import annotations

from relay.listgroups import (
    COMPLETING,
    DEAD,
    EMPTY,
    PREPARING,
    STABLE,
    GroupInfo,
    GroupList,
)


def _fleet():
    return GroupList(
        groups=[
            GroupInfo("orders", STABLE, members=4, offset_age_ticks=0),
            GroupInfo("billing", STABLE, members=2, offset_age_ticks=0),
            GroupInfo("stale", EMPTY, members=0, offset_age_ticks=5000),
            GroupInfo("fresh-empty", EMPTY, members=0, offset_age_ticks=10),
            GroupInfo("stuck", PREPARING, members=3, offset_age_ticks=9000),
            GroupInfo("gone", DEAD, members=0, offset_age_ticks=0),
        ]
    )


class TestVisibility:
    def test_a_dead_group_is_not_listed(self):
        ids = [g.group_id for g in _fleet().visible()]
        assert "gone" not in ids
        assert len(ids) == 5

    def test_filtering_by_state(self):
        assert len(_fleet().in_state(STABLE)) == 2


class TestStuck:
    def test_a_long_rebalance_is_stuck(self):
        assert _fleet().stuck_rebalancing(threshold=1000) == ["stuck"]

    def test_a_completing_group_under_threshold_is_not_stuck(self):
        gl = GroupList(
            groups=[GroupInfo("g", COMPLETING, members=2, offset_age_ticks=50)]
        )
        assert gl.stuck_rebalancing(threshold=1000) == []


class TestDeletable:
    def test_an_aged_empty_group_is_deletable(self):
        assert _fleet().deletable_empty(offset_age_limit=1000) == ["stale"]

    def test_a_fresh_empty_group_is_kept(self):
        assert "fresh-empty" not in _fleet().deletable_empty(1000)


class TestByState:
    def test_the_counts_exclude_dead(self):
        note = _fleet().by_state()
        assert "Stable: 2" in note
        assert "Empty: 2" in note
        assert "Dead" not in note
