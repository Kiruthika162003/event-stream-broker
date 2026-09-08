from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.lamportclock import LamportClock


class TestTick:
    def test_a_local_event_increments(self):
        c = LamportClock(node_id=1)
        assert c.tick() == 1
        assert c.tick() == 2


class TestReceive:
    def test_receive_advances_past_the_message(self):
        c = LamportClock(node_id=1, counter=3)
        # message from a further-ahead node
        assert c.on_receive(message_timestamp=10) == 11

    def test_receive_from_behind_still_advances_by_one(self):
        c = LamportClock(node_id=1, counter=10)
        assert c.on_receive(message_timestamp=2) == 11

    def test_a_negative_received_timestamp_is_refused(self):
        c = LamportClock(node_id=1)
        with pytest.raises(Invalid):
            c.on_receive(-1)


class TestCausality:
    def test_a_send_precedes_its_receive(self):
        sender = LamportClock(node_id=1)
        send_ts = sender.tick()
        receiver = LamportClock(node_id=2, counter=0)
        recv_ts = receiver.on_receive(send_ts)
        assert send_ts < recv_ts


class TestTotalOrder:
    def test_ties_break_by_node_id(self):
        a = (5, 1)
        b = (5, 2)
        assert LamportClock.happens_before(a, b)
        assert not LamportClock.happens_before(b, a)


class TestConfig:
    def test_a_negative_node_id_is_refused(self):
        with pytest.raises(Invalid):
            LamportClock(node_id=-1)
