from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.membershipchange import Membership


class TestChange:
    def test_adding_one_voter_is_safe(self):
        m = Membership(voters={"a", "b", "c"})
        note = m.change_to({"a", "b", "c", "d"})
        assert "majority 2 -> 3" in note
        assert m.voters == {"a", "b", "c", "d"}

    def test_removing_one_voter_is_safe(self):
        m = Membership(voters={"a", "b", "c"})
        m.change_to({"a", "b"})
        assert m.voters == {"a", "b"}

    def test_changing_two_at_once_is_refused(self):
        m = Membership(voters={"a", "b", "c"})
        with pytest.raises(Invalid) as caught:
            m.change_to({"a", "b", "c", "d", "e"})
        assert "split brain" in str(caught.value)

    def test_an_empty_target_is_refused(self):
        m = Membership(voters={"a"})
        with pytest.raises(Invalid):
            m.change_to(set())

    def test_no_change_is_a_noop(self):
        m = Membership(voters={"a", "b", "c"})
        assert m.change_to({"a", "b", "c"}) == "no change"


class TestFailures:
    def test_growing_raises_the_failures_tolerated(self):
        m = Membership(voters={"a", "b", "c"})
        assert m.failures_tolerated() == 1
        m.change_to({"a", "b", "c", "d"})
        m.change_to({"a", "b", "c", "d", "e"})
        assert m.failures_tolerated() == 2


class TestConfig:
    def test_an_empty_initial_set_is_refused(self):
        with pytest.raises(Invalid):
            Membership(voters=set())
