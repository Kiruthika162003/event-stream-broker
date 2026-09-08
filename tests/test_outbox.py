from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.outbox import OutboxRelay


class TestPublish:
    def test_publishing_marks_a_row_after_the_ack(self):
        r = OutboxRelay()
        r.enqueue(1, "created")
        note = r.publish_next(broker_acked=True)
        assert "published row 1" in note
        assert 1 in r.published

    def test_marking_before_the_ack_is_refused(self):
        r = OutboxRelay()
        r.enqueue(1, "created")
        with pytest.raises(Invalid) as caught:
            r.publish_next(broker_acked=False)
        assert "drop the event on a relay crash" in str(caught.value)

    def test_publishing_is_in_insertion_order(self):
        r = OutboxRelay()
        r.enqueue(1, "a")
        r.enqueue(2, "b")
        assert "row 1" in r.publish_next(broker_acked=True)
        assert "row 2" in r.publish_next(broker_acked=True)

    def test_an_empty_outbox_is_drained(self):
        assert "drained" in OutboxRelay().publish_next(broker_acked=True)


class TestMark:
    def test_a_double_publish_is_refused(self):
        r = OutboxRelay()
        r.enqueue(1, "a")
        r.mark_published(1)
        with pytest.raises(Invalid) as caught:
            r.mark_published(1)
        assert "already published" in str(caught.value)


class TestBacklog:
    def test_the_backlog_counts_unpublished(self):
        r = OutboxRelay()
        r.enqueue(1, "a")
        r.enqueue(2, "b")
        r.publish_next(broker_acked=True)
        assert "1 unpublished outbox row(s)" in r.backlog()
