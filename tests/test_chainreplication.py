from __future__ import annotations

import pytest

from relay.chainreplication import ChainReplication
from relay.errors import Invalid


def _chain():
    return ChainReplication(chain=["h", "m1", "m2", "t"])


class TestRouting:
    def test_a_write_enters_at_the_head(self):
        assert "accepted at head 'h'" in _chain().write("h")

    def test_a_write_elsewhere_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _chain().write("m1")
        assert "enter at the head" in str(caught.value)

    def test_a_read_is_served_by_the_tail(self):
        assert "served by tail 't'" in _chain().read("t")

    def test_a_read_from_a_middle_node_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _chain().read("m1")
        assert "not committed" in str(caught.value)


class TestFailure:
    def test_head_failure_promotes_the_next(self):
        c = _chain()
        assert "new head" in c.fail("h")
        assert c.head() == "m1"

    def test_tail_failure_promotes_the_predecessor(self):
        c = _chain()
        note = c.fail("t")
        assert "promoted" in note
        assert c.tail() == "m2"

    def test_middle_failure_is_repaired(self):
        c = _chain()
        assert "chain repaired" in c.fail("m1")
        assert c.chain == ["h", "m2", "t"]


class TestConfig:
    def test_an_empty_chain_is_refused(self):
        with pytest.raises(Invalid):
            ChainReplication(chain=[])

    def test_report_names_head_and_tail(self):
        note = _chain().report()
        assert "head 'h'" in note
        assert "tail 't'" in note
