from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.preallocation import (
    PreallocatedSegment,
    PreallocationReport,
)


class TestAppend:
    def test_appends_write_into_reserved_space(self):
        seg = PreallocatedSegment(reserved=1000)
        assert "500/1000" in seg.append(500)
        assert "800/1000" in seg.append(300)

    def test_exceeding_the_reservation_rolls(self):
        seg = PreallocatedSegment(reserved=1000)
        seg.append(900)
        with pytest.raises(Invalid) as caught:
            seg.append(200)
        assert "the disk-full failure happens cleanly" in str(
            caught.value
        )

    def test_a_zero_reservation_is_refused(self):
        with pytest.raises(Invalid):
            PreallocatedSegment(reserved=0)


class TestSeal:
    def test_sealing_reclaims_the_unused_tail(self):
        seg = PreallocatedSegment(reserved=1000)
        seg.append(300)
        verdict = seg.seal()
        assert "700 reserved byte(s) returned" in verdict
        assert seg.reserved == 300

    def test_a_sealed_segment_refuses_appends(self):
        seg = PreallocatedSegment(reserved=1000)
        seg.seal()
        with pytest.raises(Invalid):
            seg.append(10)


class TestReport:
    def test_the_report_separates_reserved_from_used(self):
        report = PreallocationReport(
            segments=[
                PreallocatedSegment(reserved=1000, used=300),
                PreallocatedSegment(reserved=1000, used=100),
            ]
        )
        totals = report.totals()
        assert "2000 reserved, 400 used, 1600" in totals
        assert "reserved-but-empty told apart" in totals
