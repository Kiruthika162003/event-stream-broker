from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.pauseresume import PartitionFlow


def flow() -> PartitionFlow:
    return PartitionFlow(assigned={0, 1, 2})


class TestPausing:
    def test_pause_holds_position_without_unassigning(self):
        chosen = flow()
        assert "paused, position held" in chosen.pause(1)
        assert 1 in chosen.assigned
        assert chosen.fetchable() == {0, 2}

    def test_pausing_an_unassigned_partition_is_refused(self):
        with pytest.raises(Invalid) as caught:
            flow().pause(9)
        assert "does not acquire ownership" in str(caught.value)

    def test_pause_is_idempotent(self):
        chosen = flow()
        chosen.pause(1)
        assert "already paused" in chosen.pause(1)


class TestResuming:
    def test_resume_restores_fetchability(self):
        chosen = flow()
        chosen.pause(1)
        chosen.resume(1)
        assert chosen.fetchable() == {0, 1, 2}

    def test_resuming_an_unpaused_partition_is_boring(self):
        assert "was not paused" in flow().resume(0)

    def test_resuming_an_unassigned_partition_is_refused(self):
        with pytest.raises(Invalid):
            flow().resume(9)


class TestLagVisibility:
    def test_a_paused_partition_still_counts_lag(self):
        chosen = flow()
        chosen.pause(1)
        verdict = chosen.lag_still_counts({1: 500, 0: 0})
        assert "1 paused partition(s) still accruing lag" in (
            verdict
        )
        assert "must not mistake the two" in verdict

    def test_no_paused_lag_reports_calm(self):
        chosen = flow()
        chosen.pause(1)
        assert "no paused partition is accruing lag" in (
            chosen.lag_still_counts({1: 0})
        )
