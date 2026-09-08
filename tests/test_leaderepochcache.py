from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.leaderepochcache import LeaderEpochCache


class TestAssign:
    def test_increasing_epochs_accumulate(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(1, 40)
        assert len(c.entries) == 2

    def test_a_backwards_epoch_is_refused(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(5, 0)
        with pytest.raises(Invalid) as caught:
            c.assign(3, 40)
        assert "only ever increases" in str(caught.value)


class TestEndOffsetFor:
    def test_an_epoch_ends_where_the_next_begins(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(1, 40)
        c.assign(2, 70)
        assert c.end_offset_for(0) == 40
        assert c.end_offset_for(1) == 70

    def test_the_current_epoch_ends_at_the_log_end(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(2, 70)
        assert c.end_offset_for(2) == 100

    def test_a_gap_epoch_resolves_to_the_next_boundary(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(2, 70)
        # epoch 1 never led; the follower must not pass epoch 2's start
        assert c.end_offset_for(1) == 70

    def test_an_epoch_older_than_the_cache_falls_back(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(5, 50)
        with pytest.raises(Missing) as caught:
            c.end_offset_for(1)
        assert "fall back to the log start" in str(caught.value)


class TestTruncate:
    def test_truncation_drops_epochs_above_the_point(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(1, 40)
        c.assign(2, 70)
        dropped = c.truncate_from(50)
        assert dropped == 1
        assert c.log_end == 50

    def test_drop_below_keeps_at_least_the_last_epoch(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(0, 0)
        c.assign(1, 40)
        c.drop_below(200)
        assert len(c.entries) == 1


class TestSpan:
    def test_the_span_names_the_retained_epochs(self):
        c = LeaderEpochCache(log_end=100)
        c.assign(3, 0)
        c.assign(7, 40)
        assert "epochs 3..7 retained" in c.span()

    def test_an_empty_cache_truncates_to_the_log_start(self):
        c = LeaderEpochCache()
        assert "truncates to the log start" in c.span()
