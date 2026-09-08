from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logcleaner import DirtyLog, LogCleaner


def logs() -> list[DirtyLog]:
    return [
        DirtyLog(partition=0, total_records=1000, superseded_records=100),
        DirtyLog(partition=1, total_records=200, superseded_records=180),
        DirtyLog(partition=2, total_records=500, superseded_records=250),
    ]


class TestRanking:
    def test_the_dirtiest_log_ranks_first(self):
        cleaner = LogCleaner(min_dirty_ratio=0.2)
        ranked = cleaner.rank(logs())
        assert ranked[0].partition == 1
        assert ranked[1].partition == 2

    def test_below_the_floor_logs_are_excluded(self):
        cleaner = LogCleaner(min_dirty_ratio=0.2)
        ranked = cleaner.rank(logs())
        assert all(
            log.dirty_ratio() >= 0.2 for log in ranked
        )
        assert 0 not in [log.partition for log in ranked]

    def test_the_ratio_is_scale_free(self):
        tiny = DirtyLog(1, total_records=10, superseded_records=9)
        huge = DirtyLog(2, total_records=100000, superseded_records=90000)
        assert tiny.dirty_ratio() == pytest.approx(0.9)
        assert huge.dirty_ratio() == pytest.approx(0.9)


class TestCleaning:
    def test_a_dirty_log_is_compacted(self):
        cleaner = LogCleaner(min_dirty_ratio=0.2)
        verdict = cleaner.clean(logs()[1])
        assert "reclaimed 180 of 200 records" in verdict
        assert cleaner.records_reclaimed == 180

    def test_a_clean_log_is_skipped_with_the_reason(self):
        cleaner = LogCleaner(min_dirty_ratio=0.2)
        verdict = cleaner.clean(logs()[0])
        assert "below the 20% floor" in verdict
        assert "competes with live traffic for nothing" in verdict


class TestEfficiency:
    def test_the_efficiency_rates_reclaim_against_work(self):
        cleaner = LogCleaner(min_dirty_ratio=0.2)
        cleaner.clean(logs()[1])
        cleaner.clean(logs()[2])
        report = cleaner.efficiency()
        assert "430 reclaimed for 700 processed" in report
        assert "costume of diligence" in report

    def test_a_bad_floor_is_refused(self):
        with pytest.raises(Invalid):
            LogCleaner(min_dirty_ratio=0)
