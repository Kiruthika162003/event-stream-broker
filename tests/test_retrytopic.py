from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.retrytopic import DEAD_LETTER, RetryRouter


def _router():
    return RetryRouter(tier_delays=[5, 30, 300])


class TestRoute:
    def test_a_failure_goes_to_the_matching_tier(self):
        r = _router()
        assert r.route_on_failure(0) == "retry-tier-0"
        assert r.route_on_failure(2) == "retry-tier-2"

    def test_exhausting_the_tiers_goes_to_the_dead_letter(self):
        assert _router().route_on_failure(3) == DEAD_LETTER

    def test_a_negative_attempt_is_refused(self):
        with pytest.raises(Invalid):
            _router().route_on_failure(-1)


class TestDelay:
    def test_each_tier_has_its_delay(self):
        r = _router()
        assert r.delay_for(0) == 5
        assert r.delay_for(2) == 300

    def test_a_dead_letter_has_no_delay(self):
        with pytest.raises(Invalid):
            _router().delay_for(3)


class TestConfig:
    def test_no_tiers_is_refused(self):
        with pytest.raises(Invalid):
            RetryRouter(tier_delays=[])

    def test_a_negative_delay_is_refused(self):
        with pytest.raises(Invalid):
            RetryRouter(tier_delays=[5, -1])


class TestReport:
    def test_a_mid_tier_report_names_the_delay(self):
        note = _router().report(1)
        assert "on retry-tier-1, waiting 30" in note

    def test_the_exhausted_report_names_the_dlq(self):
        note = _router().report(3)
        assert "to the dead-letter for a human" in note

    def test_success_is_not_escalated(self):
        assert "not escalated" in _router().on_success(1)
