from __future__ import annotations

import pytest

from relay.consumerclose import ConsumerClose
from relay.errors import Invalid


class TestClose:
    def test_a_clean_close_commits_then_leaves(self):
        c = ConsumerClose(position=500)
        note = c.close()
        assert "committed final offset 500" in note
        assert "rebalances now" in note
        assert c.committed == 500
        assert c.left_group

    def test_poll_after_close_is_refused(self):
        c = ConsumerClose(position=500)
        c.close()
        with pytest.raises(Invalid) as caught:
            c.poll()
        assert "consumer is closing" in str(caught.value)

    def test_a_double_close_is_refused(self):
        c = ConsumerClose(position=500)
        c.close()
        with pytest.raises(Invalid) as caught:
            c.close()
        assert "already closed" in str(caught.value)


class TestPoll:
    def test_poll_works_before_close(self):
        c = ConsumerClose(position=0)
        assert c.poll() == "polled"


class TestCrashedCost:
    def test_it_names_the_session_timeout_gap(self):
        note = ConsumerClose.crashed_cost(session_timeout=45000)
        assert "45000 session timeout" in note
        assert "consumed by no one" in note
