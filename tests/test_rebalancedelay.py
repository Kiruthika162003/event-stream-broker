from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rebalancedelay import RebalanceDelay


class TestCollecting:
    def test_the_first_join_starts_the_delay(self):
        d = RebalanceDelay(base_delay=3, max_delay=10)
        assert "collecting until 3" in d.on_join(now=0)

    def test_more_joins_batch_and_extend(self):
        d = RebalanceDelay(base_delay=3, max_delay=10)
        d.on_join(now=0)
        note = d.on_join(now=2)  # extends to 2+3=5
        assert "2 batched" in note
        assert "collecting until 5" in note

    def test_the_extension_is_capped(self):
        d = RebalanceDelay(base_delay=3, max_delay=5)
        d.on_join(now=0)
        d.on_join(now=4)  # would extend to 7 but cap is 0+5=5
        assert d.ready_at == 5


class TestReady:
    def test_not_ready_before_the_delay(self):
        d = RebalanceDelay(base_delay=3, max_delay=10)
        d.on_join(now=0)
        assert not d.ready(now=2)

    def test_ready_after_the_delay(self):
        d = RebalanceDelay(base_delay=3, max_delay=10)
        d.on_join(now=0)
        assert d.ready(now=3)
        assert "rebalancing once" in d.status(now=3)


class TestConfig:
    def test_a_cap_below_the_base_is_refused(self):
        with pytest.raises(Invalid):
            RebalanceDelay(base_delay=10, max_delay=5)

    def test_an_empty_group_has_no_rebalance(self):
        d = RebalanceDelay(base_delay=3, max_delay=10)
        assert "no rebalance pending" in d.status(now=0)
