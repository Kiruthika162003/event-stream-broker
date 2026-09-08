from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.filehandles import FileHandleBudget


class TestTotals:
    def test_segment_fds_multiply_by_files_per_segment(self):
        b = FileHandleBudget(limit=10000, open_segments=100)
        assert b.segment_fds() == 300

    def test_total_adds_connections(self):
        b = FileHandleBudget(limit=10000, open_segments=100, connections=50)
        assert b.total() == 350
        assert b.headroom() == 9650


class TestRisk:
    def test_over_the_limit_is_an_outage(self):
        b = FileHandleBudget(limit=300, open_segments=100, connections=50)
        assert "OVER" in b.report()

    def test_at_risk_near_the_limit(self):
        b = FileHandleBudget(limit=1000, open_segments=300, connections=0)
        # 900/1000 = 0.9 -> at risk
        assert b.at_risk()
        assert "AT RISK" in b.report()

    def test_segments_dominant_points_at_retention(self):
        b = FileHandleBudget(limit=10000, open_segments=1000, connections=5)
        assert "retention or segment sizing" in b.report()

    def test_connections_dominant_points_at_the_quota(self):
        b = FileHandleBudget(limit=10000, open_segments=1, connections=500)
        assert "connection quota" in b.report()


class TestConfig:
    def test_zero_files_per_segment_is_refused(self):
        with pytest.raises(Invalid):
            FileHandleBudget(limit=100, open_segments=1, files_per_segment=0)

    def test_a_bad_limit_is_refused(self):
        with pytest.raises(Invalid):
            FileHandleBudget(limit=0, open_segments=1)
