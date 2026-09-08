from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.grouptype import GroupTypeRegistry


class TestJoin:
    def test_the_first_member_types_the_group(self):
        g = GroupTypeRegistry()
        assert "typed as 'consumer'" in g.join("consumer")

    def test_a_matching_member_joins(self):
        g = GroupTypeRegistry()
        g.join("consumer")
        assert "stays homogeneous" in g.join("consumer")

    def test_a_mismatched_type_is_refused(self):
        g = GroupTypeRegistry()
        g.join("consumer")
        with pytest.raises(Invalid) as caught:
            g.join("connect")
        assert "wrong group id" in str(caught.value)

    def test_an_empty_type_is_refused(self):
        g = GroupTypeRegistry()
        with pytest.raises(Invalid):
            g.join("")


class TestLeaveAndReuse:
    def test_an_emptied_group_can_be_retyped(self):
        g = GroupTypeRegistry()
        g.join("consumer")
        g.leave()
        assert "typed as 'connect'" in g.join("connect")

    def test_leaving_with_members_left_keeps_the_type(self):
        g = GroupTypeRegistry()
        g.join("consumer")
        g.join("consumer")
        assert "still 'consumer'" in g.leave()


class TestCurrentType:
    def test_an_empty_group_is_untyped(self):
        assert "untyped" in GroupTypeRegistry().current_type()

    def test_a_typed_group_reports_its_type(self):
        g = GroupTypeRegistry()
        g.join("consumer")
        assert "'consumer' with 1 member(s)" in g.current_type()
