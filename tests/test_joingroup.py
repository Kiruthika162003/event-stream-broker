from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.joingroup import JoinPhase


class TestJoin:
    def test_the_first_joiner_is_the_leader(self):
        j = JoinPhase(generation=5)
        assert "joined as leader" in j.join("c1", ["range"])
        assert "joined as follower" in j.join("c2", ["range"])
        assert j.leader() == "c1"

    def test_a_late_member_folds_into_the_next_generation(self):
        j = JoinPhase(generation=5)
        j.join("c1", ["range"])
        j.close_window()
        note = j.join("c2", ["range"])
        assert "generation 6, not this one" in note
        assert "c2" not in j.members


class TestChooseStrategy:
    def test_it_picks_the_common_ground(self):
        j = JoinPhase(generation=1)
        j.join("new", ["cooperative-sticky", "range"])
        j.join("old", ["range"])
        assert j.choose_strategy() == "range"

    def test_it_honors_the_leaders_preference_order(self):
        j = JoinPhase(generation=1)
        j.join("c1", ["cooperative-sticky", "range"])
        j.join("c2", ["cooperative-sticky", "range"])
        assert j.choose_strategy() == "cooperative-sticky"

    def test_no_common_strategy_is_refused(self):
        j = JoinPhase(generation=1)
        j.join("c1", ["cooperative-sticky"])
        j.join("c2", ["range"])
        with pytest.raises(Invalid) as caught:
            j.choose_strategy()
        assert "common to all members" in str(caught.value)


class TestCloseWindow:
    def test_closing_names_leader_and_strategy(self):
        j = JoinPhase(generation=3)
        j.join("c1", ["range"])
        j.join("c2", ["range"])
        note = j.close_window()
        assert "leader c1" in note
        assert "strategy range" in note
        assert "2 member(s)" in note

    def test_a_leaderless_group_has_no_assignment(self):
        j = JoinPhase(generation=3)
        with pytest.raises(Invalid):
            j.choose_strategy()
