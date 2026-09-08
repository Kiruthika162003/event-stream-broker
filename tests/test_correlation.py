from __future__ import annotations

import pytest

from relay.correlation import CorrelationTracker
from relay.errors import Invalid


class TestSendReceive:
    def test_ids_increase_per_connection(self):
        t = CorrelationTracker()
        assert t.send() == 0
        assert t.send() == 1

    def test_responses_matched_in_order(self):
        t = CorrelationTracker()
        a = t.send()
        b = t.send()
        assert "matched response 0" in t.receive(a)
        assert "matched response 1" in t.receive(b)


class TestFaults:
    def test_an_unknown_id_is_refused(self):
        t = CorrelationTracker()
        t.send()
        with pytest.raises(Invalid) as caught:
            t.receive(999)
        assert "not outstanding" in str(caught.value)

    def test_an_out_of_order_response_is_refused(self):
        t = CorrelationTracker()
        t.send()  # id 0
        t.send()  # id 1
        with pytest.raises(Invalid) as caught:
            t.receive(1)
        assert "desynchronized" in str(caught.value)

    def test_a_duplicate_response_is_refused(self):
        t = CorrelationTracker()
        a = t.send()
        t.receive(a)
        with pytest.raises(Invalid):
            t.receive(a)


class TestDepth:
    def test_depth_counts_in_flight(self):
        t = CorrelationTracker()
        t.send()
        t.send()
        assert "2 request(s) in flight" in t.depth()
