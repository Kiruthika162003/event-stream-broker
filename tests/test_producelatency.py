from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.producelatency import ProduceLatency


def _lat():
    return ProduceLatency(
        queue_ms=2,
        append_ms=3,
        follower_acks_ms=[5, 8, 20],
    )


class TestLatency:
    def test_acks_leader_excludes_replication(self):
        assert _lat().latency(acks_all=False) == 5

    def test_acks_all_adds_the_slowest_follower(self):
        # queue 2 + append 3 + slowest follower 20 = 25
        assert _lat().latency(acks_all=True) == 25

    def test_replication_wait_is_the_slowest_not_the_mean(self):
        assert _lat().replication_wait() == 20


class TestDominant:
    def test_replication_dominates_for_acks_all(self):
        note = _lat().dominant_stage(acks_all=True)
        assert "replication dominates" in note
        assert "lagging follower" in note

    def test_append_can_dominate_for_acks_leader(self):
        lat = ProduceLatency(queue_ms=1, append_ms=10, follower_acks_ms=[2])
        assert "append dominates" in lat.dominant_stage(acks_all=False)


class TestRefusals:
    def test_a_negative_stage_is_refused(self):
        with pytest.raises(Invalid):
            ProduceLatency(queue_ms=-1, append_ms=2)


class TestReport:
    def test_report_names_mode_and_breakdown(self):
        note = _lat().report(acks_all=True)
        assert "acks=all latency 25.0ms" in note
