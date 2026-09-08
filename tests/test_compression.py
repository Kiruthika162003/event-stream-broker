from __future__ import annotations

import pytest

from relay.compression import (
    Workload,
    cpu_cost,
    effective_ratio,
    recommend_codec,
)
from relay.errors import Invalid


class TestRecommendation:
    def test_network_bound_spends_cpu_for_ratio(self):
        rec = recommend_codec(
            Workload("network", avg_batch_records=64)
        )
        assert "codec high" in rec
        assert "expensive link" in rec

    def test_cpu_bound_uses_a_fast_codec(self):
        rec = recommend_codec(
            Workload("cpu", avg_batch_records=64)
        )
        assert "codec fast" in rec
        assert "false economy" in rec

    def test_tiny_batches_need_batching_first(self):
        rec = recommend_codec(
            Workload("network", avg_batch_records=2)
        )
        assert "fix batching first" in rec
        assert "raise linger, not the codec" in rec

    def test_a_bad_workload_is_refused(self):
        with pytest.raises(Invalid):
            Workload("disk", avg_batch_records=10)


class TestRatioAndCost:
    def test_full_batches_realize_the_nominal_ratio(self):
        assert effective_ratio("high", batch_records=64) == 4.0

    def test_tiny_batches_realize_only_a_fraction(self):
        assert effective_ratio("high", batch_records=2) < 4.0
        assert effective_ratio("high", batch_records=2) > 1.0

    def test_cpu_cost_rises_with_ratio(self):
        assert cpu_cost("none") < cpu_cost("fast") < cpu_cost("high")

    def test_an_unknown_codec_is_refused(self):
        with pytest.raises(Invalid):
            effective_ratio("magic", 10)
