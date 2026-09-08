from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rebalance import (
    naive_moved,
    sticky_assign,
)

PARTS = list(range(12))


class TestBalance:
    def test_the_first_assignment_is_balanced(self):
        assignment, _ = sticky_assign(PARTS, ["c1", "c2", "c3"])
        assert assignment.balanced()
        assert all(
            len(v) == 4 for v in assignment.by_member.values()
        )

    def test_uneven_counts_differ_by_at_most_one(self):
        assignment, _ = sticky_assign(
            list(range(10)), ["c1", "c2", "c3"]
        )
        counts = sorted(
            len(v) for v in assignment.by_member.values()
        )
        assert counts == [3, 3, 4]

    def test_an_empty_group_is_refused(self):
        with pytest.raises(Invalid):
            sticky_assign(PARTS, [])


class TestStickiness:
    def test_adding_a_member_moves_only_what_must_move(self):
        first, _ = sticky_assign(PARTS, ["c1", "c2", "c3"])
        second, moved = sticky_assign(
            PARTS, ["c1", "c2", "c3", "c4"], previous=first
        )
        assert moved == 3
        assert second.balanced()

    def test_sticky_beats_naive_on_the_same_change(self):
        first, _ = sticky_assign(PARTS, ["c1", "c2", "c3"])
        _, sticky = sticky_assign(
            PARTS, ["c1", "c2", "c3", "c4"], previous=first
        )
        naive = naive_moved(PARTS, ["c1", "c2", "c3", "c4"], first)
        assert sticky == 3
        assert naive == 9
        assert sticky < naive

    def test_a_stable_membership_moves_nothing(self):
        first, _ = sticky_assign(PARTS, ["c1", "c2", "c3"])
        _, moved = sticky_assign(
            PARTS, ["c1", "c2", "c3"], previous=first
        )
        assert moved == 0


class TestOwnership:
    def test_owner_lookup_finds_the_holder(self):
        assignment, _ = sticky_assign(PARTS, ["c1", "c2"])
        owner = assignment.owner_of(0)
        assert owner in ("c1", "c2")
        assert assignment.owner_of(999) is None
