from __future__ import annotations

import pytest

from relay.downconvert import ConversionTracker
from relay.errors import Invalid


class TestServing:
    def test_a_matching_format_is_zero_copy(self):
        tracker = ConversionTracker()
        verdict = tracker.serve(client_format=3, broker_format=3)
        assert "zero-copy" in verdict
        assert "no application memory touched" in verdict
        assert tracker.zero_copy_fetches == 1

    def test_an_older_client_forces_down_conversion(self):
        tracker = ConversionTracker()
        verdict = tracker.serve(client_format=1, broker_format=3)
        assert "down-converted v3 -> v1" in verdict
        assert "zero-copy lost" in verdict
        assert tracker.down_converted_fetches == 1

    def test_a_client_newer_than_the_broker_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ConversionTracker().serve(
                client_format=5, broker_format=3
            )
        assert "upgrade the broker first" in str(caught.value)


class TestThePremium:
    def test_the_premium_is_a_number_before_an_incident(self):
        tracker = ConversionTracker()
        for _ in range(3):
            tracker.serve(1, 3)
        tracker.serve(3, 3)
        report = tracker.cpu_premium()
        assert "3 of 4 fetches down-converted (75%)" in report
        assert "15 CPU unit(s) of premium" in report
        assert "upgrade the clients" in report

    def test_no_fetches_cannot_be_priced(self):
        with pytest.raises(Invalid):
            ConversionTracker().cpu_premium()


class TestSubsidizing:
    def test_a_majority_down_converted_broker_is_subsidizing(self):
        tracker = ConversionTracker()
        for _ in range(3):
            tracker.serve(1, 3)
        tracker.serve(3, 3)
        assert tracker.is_subsidizing()

    def test_a_healthy_broker_is_not(self):
        tracker = ConversionTracker()
        for _ in range(3):
            tracker.serve(3, 3)
        tracker.serve(1, 3)
        assert not tracker.is_subsidizing()
