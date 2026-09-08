from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.producerclose import Producer


class TestClose:
    def test_a_clean_close_flushes_all_pending(self):
        p = Producer()
        p.send("a")
        p.send("b")
        note = p.close(acked_within_deadline=2)
        assert "closed cleanly: 2 record(s) flushed" in note

    def test_records_pending_at_the_deadline_are_returned_failed(self):
        p = Producer()
        for r in ("a", "b", "c"):
            p.send(r)
        note = p.close(acked_within_deadline=1)
        assert "1 record(s) flushed, 2 failed" in note
        assert "not lost silently" in note

    def test_a_close_with_an_empty_buffer_completes_at_once(self):
        p = Producer()
        assert "none pending" in p.close(acked_within_deadline=0)


class TestRefusals:
    def test_a_send_after_close_begins_is_refused(self):
        p = Producer()
        p.send("a")
        p.close(acked_within_deadline=1)
        with pytest.raises(Invalid) as caught:
            p.send("b")
        assert "producer is closing" in str(caught.value)

    def test_a_double_close_is_refused(self):
        p = Producer()
        p.close(acked_within_deadline=0)
        with pytest.raises(Invalid) as caught:
            p.close(acked_within_deadline=0)
        assert "already closed" in str(caught.value)
