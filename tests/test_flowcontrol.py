from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.flowcontrol import FlowControl


class TestSend:
    def test_a_sender_spends_granted_credit(self):
        fc = FlowControl()
        fc.grant(5)
        assert "sent 3; 2 credit remaining" in fc.send(3)

    def test_a_send_over_credit_is_refused(self):
        fc = FlowControl()
        fc.grant(2)
        with pytest.raises(Invalid) as caught:
            fc.send(3)
        assert "the overrun flow control prevents" in str(caught.value)

    def test_processing_refills_credit(self):
        fc = FlowControl()
        fc.grant(2)
        fc.send(2)  # credit now 0
        fc.processed(2)  # receiver freed buffer
        assert "sent 1" in fc.send(1)


class TestGrant:
    def test_negative_credit_is_refused(self):
        with pytest.raises(Invalid):
            FlowControl().grant(-1)


class TestReport:
    def test_zero_credit_is_backpressure(self):
        fc = FlowControl()
        assert "back-pressure working" in fc.report()

    def test_outstanding_credit_means_receiver_ahead(self):
        fc = FlowControl()
        fc.grant(10)
        assert "keeping ahead" in fc.report()
