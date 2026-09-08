from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.histogrammerge import Histogram, fleet_versus_naive, merge


def _h(counts):
    return Histogram(boundaries=(10, 50, 100, 500), counts=tuple(counts))


class TestPercentile:
    def test_percentile_walks_the_buckets(self):
        h = _h([50, 30, 15, 5])  # 100 total; p90 -> cumulative 80,95 -> 100
        assert h.percentile(90) == 100

    def test_an_empty_histogram_is_zero(self):
        assert _h([0, 0, 0, 0]).percentile(99) == 0

    def test_a_bad_percentile_is_refused(self):
        with pytest.raises(Invalid):
            _h([1, 1, 1, 1]).percentile(150)


class TestMerge:
    def test_merge_sums_matching_buckets(self):
        merged = merge([_h([10, 20, 30, 40]), _h([5, 5, 5, 5])])
        assert merged.counts == (15, 25, 35, 45)

    def test_mismatched_boundaries_are_refused(self):
        a = Histogram(boundaries=(1, 2), counts=(1, 1))
        b = Histogram(boundaries=(1, 3), counts=(1, 1))
        with pytest.raises(Invalid) as caught:
            merge([a, b])
        assert "different bucket boundaries" in str(caught.value)

    def test_no_histograms_is_refused(self):
        with pytest.raises(Invalid):
            merge([])


class TestFleetVersusNaive:
    def test_it_shows_the_gap_from_the_averaging_trap(self):
        # one busy broker, one idle-ish, uneven load
        busy = _h([0, 0, 10, 990])
        quiet = _h([9, 1, 0, 0])
        note = fleet_versus_naive([busy, quiet], p=99)
        assert "fleet p99" in note
        assert "off by" in note
