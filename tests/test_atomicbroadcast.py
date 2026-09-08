from __future__ import annotations

import pytest

from relay.atomicbroadcast import AtomicBroadcast
from relay.errors import Invalid


class TestReceive:
    def test_in_order_messages_deliver_immediately(self):
        b = AtomicBroadcast()
        assert b.receive(0, "a") == ["a"]
        assert b.receive(1, "b") == ["b"]

    def test_an_out_of_order_message_buffers_until_the_gap_fills(self):
        b = AtomicBroadcast()
        assert b.receive(2, "c") == []
        assert b.receive(0, "a") == ["a"]
        assert b.receive(1, "b") == ["b", "c"]  # 1 fills the gap, releasing 2

    def test_a_duplicate_is_ignored(self):
        b = AtomicBroadcast()
        b.receive(0, "a")
        assert b.receive(0, "a-again") == []


class TestDeliverInOrder:
    def test_delivering_the_next_expected_works(self):
        b = AtomicBroadcast()
        assert "delivered 0" in b.deliver_in_order(0, "a")

    def test_skipping_a_sequence_is_refused(self):
        b = AtomicBroadcast()
        with pytest.raises(Invalid) as caught:
            b.deliver_in_order(5, "e")
        assert "breaks total order" in str(caught.value)


class TestReport:
    def test_report_states_the_delivered_prefix(self):
        b = AtomicBroadcast()
        b.receive(0, "a")
        b.receive(1, "b")
        assert "delivered through sequence 1" in b.report()
