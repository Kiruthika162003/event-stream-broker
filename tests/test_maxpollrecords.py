from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.maxpollrecords import PollBudget


class TestSafeMax:
    def test_light_processing_allows_a_large_batch(self):
        # 300000 ms interval, 1 ms/record, 20% margin -> 240000
        b = PollBudget(poll_interval=300000, per_record_time=1)
        assert b.safe_max_records() == 240000

    def test_heavy_processing_allows_only_a_small_batch(self):
        # 300000 ms interval, 1000 ms/record -> 240
        b = PollBudget(poll_interval=300000, per_record_time=1000)
        assert b.safe_max_records() == 240


class TestRefusals:
    def test_a_record_slower_than_the_interval_is_refused(self):
        with pytest.raises(Invalid) as caught:
            PollBudget(poll_interval=1000, per_record_time=1000)
        assert "no" in str(caught.value)
        assert "batch size is safe" in str(caught.value)

    def test_a_bad_margin_is_refused(self):
        with pytest.raises(Invalid):
            PollBudget(poll_interval=1000, per_record_time=1, margin=1.5)


class TestKick:
    def test_an_oversized_batch_would_kick(self):
        b = PollBudget(poll_interval=1000, per_record_time=10)
        assert b.would_kick(configured=200)

    def test_a_safe_batch_does_not_kick(self):
        b = PollBudget(poll_interval=1000, per_record_time=10)
        assert not b.would_kick(configured=50)


class TestHeadroom:
    def test_headroom_reports_slack(self):
        b = PollBudget(poll_interval=1000, per_record_time=10)
        note = b.headroom(configured=50)
        assert "500 headroom" in note

    def test_over_the_limit_reports_the_kick(self):
        b = PollBudget(poll_interval=1000, per_record_time=10)
        note = b.headroom(configured=200)
        assert "over by 1000" in note
        assert "a rebalance it caused" in note
