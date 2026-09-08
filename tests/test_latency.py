from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.latency import LatencyHistogram


class TestPercentiles:
    def test_a_rare_outlier_shows_at_p999_not_p99(self):
        h = LatencyHistogram(bucket_ms=10)
        for _ in range(99):
            h.observe(5)
        h.observe(2000)
        assert h.percentile(99) == 0
        assert h.percentile(99.9) == 2000

    def test_a_common_tail_reaches_p99(self):
        h = LatencyHistogram(bucket_ms=10)
        for _ in range(90):
            h.observe(5)
        for _ in range(10):
            h.observe(900)
        assert h.percentile(99) == 900

    def test_a_bad_percentile_is_refused(self):
        h = LatencyHistogram(bucket_ms=10)
        h.observe(5)
        with pytest.raises(Invalid):
            h.percentile(0)

    def test_no_samples_cannot_be_percentiled(self):
        with pytest.raises(Invalid):
            LatencyHistogram(bucket_ms=10).percentile(50)


class TestTheReport:
    def test_a_rare_tail_reads_healthy_by_p99(self):
        h = LatencyHistogram(bucket_ms=10)
        for _ in range(99):
            h.observe(5)
        h.observe(2000)
        assert "healthy" in h.report()

    def test_a_common_tail_reads_hidden(self):
        h = LatencyHistogram(bucket_ms=10)
        for _ in range(90):
            h.observe(5)
        for _ in range(10):
            h.observe(900)
        report = h.report()
        assert "hidden tail" in report
        assert "10ms buckets" in report


class TestRefusals:
    def test_a_bad_bucket_is_refused(self):
        with pytest.raises(Invalid):
            LatencyHistogram(bucket_ms=0)

    def test_negative_latency_is_refused(self):
        with pytest.raises(Invalid):
            LatencyHistogram(bucket_ms=10).observe(-1)
