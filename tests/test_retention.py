from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.records import Record
from relay.retention import RetentionPolicy, RetentionRun
from relay.segmentlog import SegmentLog


def multi_segment_log(count: int) -> SegmentLog:
    log = SegmentLog()
    for number in range(count):
        log.append(
            Record(value=f"e{number:04}".encode() + b"x" * 500)
        )
    return log


class TestThePolicy:
    def test_a_limitless_policy_is_refused(self):
        with pytest.raises(Invalid) as caught:
            RetentionPolicy()
        assert "which is not retention" in str(caught.value)

    def test_nonpositive_limits_are_refused(self):
        with pytest.raises(Invalid):
            RetentionPolicy(max_age_ticks=0)
        with pytest.raises(Invalid):
            RetentionPolicy(max_bytes=-5)


class TestAgeAndSize:
    def test_old_sealed_segments_drop_by_age(self):
        log = multi_segment_log(20)
        ticks = {seg.base_offset: 0 for seg in log.segments}
        run = RetentionRun(
            policy=RetentionPolicy(max_age_ticks=100)
        )
        verdict = run.apply(
            log, ticks, now=1000, committed_floor=99999
        )
        # committed_floor is high so nothing above it; but floor
        # protects unread data. Use a floor past everything.
        assert "reclaimed" in verdict

    def test_the_committed_floor_outranks_the_policy(self):
        log = multi_segment_log(20)
        ticks = {seg.base_offset: 0 for seg in log.segments}
        run = RetentionRun(
            policy=RetentionPolicy(max_age_ticks=1)
        )
        verdict = run.apply(
            log, ticks, now=1000, committed_floor=0
        )
        assert "loss with a schedule" in verdict
        assert run.reclaimed_segments == 0

    def test_size_policy_drops_until_it_fits(self):
        log = multi_segment_log(20)
        ticks = {seg.base_offset: 500 for seg in log.segments}
        run = RetentionRun(
            policy=RetentionPolicy(max_bytes=5000)
        )
        verdict = run.apply(
            log, ticks, now=500, committed_floor=99999
        )
        assert run.reclaimed_segments >= 1
        assert "reclaimed" in verdict

    def test_the_union_forgets_whichever_comes_first(self):
        log = multi_segment_log(20)
        ticks = {seg.base_offset: 0 for seg in log.segments}
        run = RetentionRun(
            policy=RetentionPolicy(
                max_age_ticks=100, max_bytes=99999999
            )
        )
        run.apply(log, ticks, now=1000, committed_floor=99999)
        assert run.reclaimed_segments >= 1


class TestSparing:
    def test_a_young_within_caps_log_is_left_whole(self):
        log = multi_segment_log(20)
        ticks = {seg.base_offset: 990 for seg in log.segments}
        run = RetentionRun(
            policy=RetentionPolicy(
                max_age_ticks=100, max_bytes=99999999
            )
        )
        verdict = run.apply(
            log, ticks, now=1000, committed_floor=99999
        )
        assert "within both the age window and the size cap" in (
            verdict
        )
