from __future__ import annotations

import pytest

from relay.assignmode import NONE, SUBSCRIBED, ConsumerMode
from relay.errors import Invalid


class TestSubscribe:
    def test_subscribe_uses_the_coordinator(self):
        c = ConsumerMode()
        verdict = c.subscribe("billing")
        assert "the coordinator assigns and rebalances" in verdict
        assert c.mode == SUBSCRIBED

    def test_subscribe_while_assigned_is_refused(self):
        c = ConsumerMode()
        c.assign({0, 1})
        with pytest.raises(Invalid) as caught:
            c.subscribe("billing")
        assert "Unassign first" in str(caught.value)


class TestAssign:
    def test_assign_takes_specific_partitions(self):
        c = ConsumerMode()
        verdict = c.assign({3, 4})
        assert "assigned [3, 4]" in verdict
        assert "manual failure handling" in verdict
        assert c.partitions == {3, 4}

    def test_assign_while_subscribed_is_refused(self):
        c = ConsumerMode()
        c.subscribe("billing")
        with pytest.raises(Invalid) as caught:
            c.assign({0})
        assert "Unsubscribe first" in str(caught.value)


class TestRelease:
    def test_release_returns_to_none(self):
        c = ConsumerMode()
        c.assign({0, 1})
        verdict = c.release()
        assert "released assigned ownership" in verdict
        assert c.mode == NONE

    def test_release_permits_switching_modes(self):
        c = ConsumerMode()
        c.subscribe("billing")
        c.release()
        assert "assigned" in c.assign({0})
