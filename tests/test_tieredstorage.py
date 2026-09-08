from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.tieredstorage import TieredLog


def log_with_segments() -> TieredLog:
    log = TieredLog(local_window=100)
    log.add_local(0, 100, "d0")
    log.add_local(100, 200, "d1")
    log.add_local(200, 300, "d2")
    return log


class TestTiering:
    def test_old_segments_move_to_cold(self):
        log = log_with_segments()
        log.tier_out(now_end=300)
        assert log.tier_of(0) == "cold"
        assert log.tier_of(250) == "local"

    def test_upload_is_verified_before_the_delete(self):
        log = log_with_segments()
        log.tier_out(now_end=300)
        assert log.uploads_verified >= 1
        assert log.failed_deletes_prevented == 0

    def test_the_hot_tail_stays_local(self):
        log = log_with_segments()
        log.tier_out(now_end=250)
        assert log.tier_of(200) == "local"


class TestContinuity:
    def test_the_offset_space_is_unbroken_across_tiers(self):
        log = log_with_segments()
        log.tier_out(now_end=300)
        assert log.continuous()

    def test_an_offset_in_no_segment_is_missing(self):
        with pytest.raises(Missing):
            log_with_segments().tier_of(9999)


class TestTheRatio:
    def test_the_cold_ratio_is_the_cost_story(self):
        log = log_with_segments()
        log.tier_out(now_end=300)
        ratio = log.cold_ratio()
        assert "of 3 segment(s) cold" in ratio
        assert "cost story of tiering" in ratio

    def test_an_empty_log_cannot_be_measured(self):
        with pytest.raises(Invalid):
            TieredLog(local_window=10).cold_ratio()
