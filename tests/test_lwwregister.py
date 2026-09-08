from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lwwregister import LwwRegister


class TestWrite:
    def test_a_write_sets_the_value(self):
        r = LwwRegister()
        r.write("a", timestamp=5, node_id=1)
        assert r.value == "a"

    def test_a_stale_write_is_refused(self):
        r = LwwRegister(value="a", timestamp=5, node_id=1)
        with pytest.raises(Invalid):
            r.write("b", timestamp=3, node_id=1)


class TestMerge:
    def test_the_higher_timestamp_wins(self):
        a = LwwRegister(value="a", timestamp=5, node_id=1)
        b = LwwRegister(value="b", timestamp=7, node_id=2)
        assert a.merge(b)
        assert a.value == "b"

    def test_a_lower_timestamp_does_not_win(self):
        a = LwwRegister(value="a", timestamp=7, node_id=1)
        b = LwwRegister(value="b", timestamp=5, node_id=2)
        assert not a.merge(b)
        assert a.value == "a"

    def test_a_tie_breaks_by_node_id(self):
        a = LwwRegister(value="a", timestamp=5, node_id=1)
        b = LwwRegister(value="b", timestamp=5, node_id=2)
        assert a.merge(b)  # node 2 > node 1
        assert a.value == "b"

    def test_merge_is_order_independent(self):
        a1 = LwwRegister(value="a", timestamp=5, node_id=1)
        b1 = LwwRegister(value="b", timestamp=7, node_id=2)
        a1.merge(b1)
        b2 = LwwRegister(value="b", timestamp=7, node_id=2)
        a2 = LwwRegister(value="a", timestamp=5, node_id=1)
        b2.merge(a2)
        assert a1.value == b2.value


class TestConcurrent:
    def test_a_concurrent_write_drop_is_flagged(self):
        a = LwwRegister(value="a", timestamp=5, node_id=1)
        b = LwwRegister(value="b", timestamp=5, node_id=2)
        assert a.would_drop_concurrent(b)
        assert "silently drops the other" in a.report(b)

    def test_a_clean_supersede_is_named(self):
        a = LwwRegister(value="a", timestamp=7, node_id=1)
        b = LwwRegister(value="b", timestamp=5, node_id=2)
        assert "clean supersede" in a.report(b)
