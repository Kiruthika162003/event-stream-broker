from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.leaderstickiness import LeaderStickiness


class TestReclaim:
    def test_reclaim_after_the_hold_down(self):
        s = LeaderStickiness(hold_down=100)
        s.became_in_sync(now=0)
        assert "reclaims" in s.reclaim(now=100)

    def test_reclaim_before_the_hold_down_is_refused(self):
        s = LeaderStickiness(hold_down=100)
        s.became_in_sync(now=0)
        with pytest.raises(Invalid) as caught:
            s.reclaim(now=50)
        assert "risks a flap" in str(caught.value)

    def test_a_not_in_sync_broker_cannot_reclaim(self):
        s = LeaderStickiness(hold_down=100)
        with pytest.raises(Invalid) as caught:
            s.reclaim(now=100)
        assert "not in sync" in str(caught.value)


class TestFlap:
    def test_a_drop_resets_the_hold_down(self):
        s = LeaderStickiness(hold_down=100)
        s.became_in_sync(now=0)
        s.dropped_out()
        s.became_in_sync(now=50)
        # from 50, needs until 150; at 120 not yet
        assert not s.may_reclaim(now=120)
        assert s.may_reclaim(now=150)


class TestConfig:
    def test_a_zero_hold_down_is_refused(self):
        with pytest.raises(Invalid):
            LeaderStickiness(hold_down=0)


class TestReport:
    def test_a_resetting_hold_down_is_named_as_flapping(self):
        s = LeaderStickiness(hold_down=100)
        s.became_in_sync(now=0)
        assert "still flapping" in s.report(now=50)
