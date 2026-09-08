from __future__ import annotations

import pytest

from relay.callbackorder import CallbackDispatcher
from relay.errors import Invalid


class TestOrder:
    def test_in_order_acks_fire_immediately(self):
        d = CallbackDispatcher()
        assert d.acknowledge("t-0", 0) == [0]
        assert d.acknowledge("t-0", 1) == [1]

    def test_an_out_of_order_ack_buffers_until_the_gap_fills(self):
        d = CallbackDispatcher()
        # offset 2 arrives before 0 and 1
        assert d.acknowledge("t-0", 2) == []
        assert d.acknowledge("t-0", 0) == [0]
        # now 1 arrives, draining 1 then 2
        assert d.acknowledge("t-0", 1) == [1, 2]

    def test_partitions_are_independent(self):
        d = CallbackDispatcher()
        assert d.acknowledge("t-0", 0) == [0]
        assert d.acknowledge("t-1", 0) == [0]


class TestRefusals:
    def test_a_double_ack_is_refused(self):
        d = CallbackDispatcher()
        d.acknowledge("t-0", 0)
        with pytest.raises(Invalid) as caught:
            d.acknowledge("t-0", 0)
        assert "already acknowledged" in str(caught.value)

    def test_an_ack_behind_the_fired_point_is_refused(self):
        d = CallbackDispatcher()
        d.acknowledge("t-0", 0)
        d.acknowledge("t-0", 1)
        with pytest.raises(Invalid) as caught:
            d.acknowledge("t-0", 0)
        assert "already acknowledged" in str(caught.value)


class TestStall:
    def test_a_buffered_callback_is_a_head_of_line_stall(self):
        d = CallbackDispatcher()
        d.acknowledge("t-0", 5)
        note = d.stall_note("t-0")
        assert "1 callback(s) buffered" in note
        assert "head-of-line stall" in note

    def test_no_pending_flows_in_order(self):
        d = CallbackDispatcher()
        d.acknowledge("t-0", 0)
        assert "flow in order" in d.stall_note("t-0")
