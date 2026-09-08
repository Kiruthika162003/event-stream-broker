from __future__ import annotations

import pytest

from relay.backpressure import Pipeline, Stage
from relay.errors import Invalid


class TestBottleneck:
    def test_the_bottleneck_is_the_slowest_stage(self):
        p = Pipeline(stages=[Stage("a", 100), Stage("b", 20), Stage("c", 50)])
        assert p.bottleneck().name == "b"
        assert p.throughput() == 20

    def test_a_bounded_pipeline_is_stable(self):
        p = Pipeline(stages=[Stage("a", 100), Stage("b", 20)])
        assert p.is_stable()
        assert "stable at the bottleneck 'b'" in p.report()


class TestUnstable:
    def test_an_unbounded_buffer_is_unstable(self):
        p = Pipeline(stages=[
            Stage("a", 100),
            Stage("b", 20, bounded_buffer=False),
        ])
        assert not p.is_stable()
        note = p.report()
        assert "UNSTABLE" in note
        assert "bufferbloat failure" in note


class TestConfig:
    def test_a_zero_rate_stage_is_refused(self):
        with pytest.raises(Invalid):
            Pipeline(stages=[Stage("a", 0)])

    def test_an_empty_pipeline_is_refused(self):
        with pytest.raises(Invalid):
            Pipeline(stages=[])
