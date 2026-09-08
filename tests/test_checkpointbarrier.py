from __future__ import annotations

import pytest

from relay.checkpointbarrier import BarrierAligner
from relay.errors import Invalid


def _aligner():
    return BarrierAligner(inputs={"in1", "in2", "in3"})


class TestAlignment:
    def test_it_snapshots_only_after_all_inputs_align(self):
        a = _aligner()
        a.receive_barrier("in1", 1)
        a.receive_barrier("in2", 1)
        assert not a.aligned()
        a.receive_barrier("in3", 1)
        assert a.aligned()
        assert "checkpoint 1 snapshotted" in a.snapshot()

    def test_snapshot_before_alignment_is_refused(self):
        a = _aligner()
        a.receive_barrier("in1", 1)
        with pytest.raises(Invalid) as caught:
            a.snapshot()
        assert "inconsistent snapshot" in str(caught.value)

    def test_records_after_the_barrier_are_buffered(self):
        a = _aligner()
        a.receive_barrier("in1", 1)
        a.buffer_record("in1")  # in1 already sent its barrier
        a.receive_barrier("in2", 1)
        a.receive_barrier("in3", 1)
        note = a.snapshot()
        assert "1 buffered record(s) released" in note


class TestMonotonic:
    def test_a_non_advancing_checkpoint_is_refused(self):
        a = _aligner()
        for ch in ("in1", "in2", "in3"):
            a.receive_barrier(ch, 5)
        a.snapshot()
        with pytest.raises(Invalid) as caught:
            a.receive_barrier("in1", 5)
        assert "monotonic" in str(caught.value)

    def test_a_barrier_on_an_unknown_input_is_refused(self):
        a = _aligner()
        with pytest.raises(Invalid):
            a.receive_barrier("ghost", 1)


class TestConfig:
    def test_no_inputs_is_refused(self):
        with pytest.raises(Invalid):
            BarrierAligner(inputs=set())
