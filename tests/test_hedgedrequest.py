from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.hedgedrequest import HedgePolicy


class TestShouldHedge:
    def test_no_hedge_before_the_delay(self):
        h = HedgePolicy(hedge_delay=100)
        assert not h.should_hedge(waited=50)

    def test_hedge_after_the_delay(self):
        h = HedgePolicy(hedge_delay=100)
        assert h.should_hedge(waited=150)

    def test_no_hedge_after_a_response(self):
        h = HedgePolicy(hedge_delay=100)
        h.respond()
        assert not h.should_hedge(waited=150)


class TestHedge:
    def test_hedging_after_the_delay_works(self):
        h = HedgePolicy(hedge_delay=100)
        assert "second replica" in h.hedge(waited=150)
        assert h.hedged

    def test_hedging_before_the_delay_is_refused(self):
        h = HedgePolicy(hedge_delay=100)
        with pytest.raises(Invalid) as caught:
            h.hedge(waited=50)
        assert "must not be hedged" in str(caught.value)

    def test_hedging_after_a_response_is_refused(self):
        h = HedgePolicy(hedge_delay=100)
        h.respond()
        with pytest.raises(Invalid):
            h.hedge(waited=150)

    def test_a_response_cancels_the_hedge_copy(self):
        h = HedgePolicy(hedge_delay=100)
        h.hedge(waited=150)
        assert "hedge copy is cancelled" in h.respond()


class TestConfigAndRate:
    def test_a_zero_delay_is_refused(self):
        with pytest.raises(Invalid):
            HedgePolicy(hedge_delay=0)

    def test_a_high_hedge_rate_flags_the_delay(self):
        h = HedgePolicy(hedge_delay=100)
        assert "delay is too low" in h.expected_hedge_rate(0.4)

    def test_a_small_hedge_rate_is_intended(self):
        h = HedgePolicy(hedge_delay=100)
        assert "intended use" in h.expected_hedge_rate(0.05)
