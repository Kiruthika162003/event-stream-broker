from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.watermarkgen import WatermarkGenerator


class TestObserve:
    def test_the_watermark_trails_the_max_by_the_bound(self):
        g = WatermarkGenerator(lateness_bound=5)
        assert g.observe(100) == 95

    def test_it_only_advances(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)  # watermark 95
        # an earlier event does not pull it back
        assert g.observe(80) == 95

    def test_a_later_event_advances_it(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)
        assert g.observe(120) == 115


class TestLateness:
    def test_a_record_before_the_watermark_is_late(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)  # watermark 95
        assert g.is_late(90)

    def test_a_record_within_the_bound_is_not_late(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)
        assert not g.is_late(97)


class TestIdle:
    def test_idle_advance_moves_the_watermark_by_wall_time(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)  # watermark 95
        # source went quiet; wall clock at 200 pushes watermark to 195
        assert g.advance_on_idle(wall_now=200) == 195


class TestConfig:
    def test_a_negative_bound_is_refused(self):
        with pytest.raises(Invalid):
            WatermarkGenerator(lateness_bound=-1)

    def test_tolerance_reports_the_gap(self):
        g = WatermarkGenerator(lateness_bound=5)
        g.observe(100)
        assert "trails the max event time by 5" in g.tolerance()
