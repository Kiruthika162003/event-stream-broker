from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.topicdelete import ACTIVE, MARKED, REMOVED, TopicLifecycle


def topic() -> TopicLifecycle:
    return TopicLifecycle(name="orders", grace_ticks=100)


class TestMarking:
    def test_marking_stops_produces_but_keeps_data(self):
        t = topic()
        verdict = t.mark("admin-asha", now=0)
        assert "produces stop, data stays" in verdict
        assert t.state == MARKED
        assert not t.accepts_produce()

    def test_an_unattributed_deletion_is_refused(self):
        with pytest.raises(Invalid) as caught:
            topic().mark("  ", now=0)
        assert "audit question with no answer" in str(caught.value)

    def test_marking_a_non_active_topic_is_refused(self):
        t = topic()
        t.mark("admin", now=0)
        with pytest.raises(Invalid):
            t.mark("admin", now=1)


class TestCancellation:
    def test_a_marked_topic_can_be_un_marked(self):
        t = topic()
        t.mark("admin", now=0)
        verdict = t.cancel()
        assert "turns a typo into an outage" in verdict
        assert t.state == ACTIVE
        assert t.accepts_produce()

    def test_cancelling_an_active_topic_is_refused(self):
        with pytest.raises(Invalid):
            topic().cancel()


class TestRemoval:
    def test_removal_waits_out_the_grace_period(self):
        t = topic()
        t.mark("admin", now=0)
        with pytest.raises(Invalid) as caught:
            t.remove(now=50, uncommitted_groups=[])
        assert "still in its grace period" in str(caught.value)

    def test_removal_blocks_on_uncommitted_consumers(self):
        t = topic()
        t.mark("admin", now=0)
        with pytest.raises(Invalid) as caught:
            t.remove(now=200, uncommitted_groups=["billing"])
        assert "silently truncate their work" in str(caught.value)

    def test_a_clean_removal_keeps_the_attribution(self):
        t = topic()
        t.mark("admin-asha", now=0)
        verdict = t.remove(now=200, uncommitted_groups=[])
        assert t.state == REMOVED
        assert "admin-asha) survives the data" in verdict


class TestProduceGate:
    def test_an_active_topic_accepts_produce(self):
        assert topic().state == ACTIVE
        assert topic().accepts_produce()
