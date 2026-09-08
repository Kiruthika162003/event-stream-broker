from __future__ import annotations

import pytest

from relay.epochfetch import DivergenceGuard, truncation_point
from relay.errors import Invalid


class TestTruncationPoint:
    def test_a_prefix_log_needs_no_truncation(self):
        point, note = truncation_point(
            follower_epoch=4, follower_end=900, leader_epoch_end=1000
        )
        assert point == 900
        assert "nothing diverged" in note

    def test_a_divergent_log_truncates_to_the_boundary(self):
        point, note = truncation_point(
            follower_epoch=4, follower_end=1040, leader_epoch_end=1000
        )
        assert point == 1000
        assert "truncate 40 record(s)" in note
        assert "nothing promised is lost" in note
        assert "old leader was lagging" in note


class TestDivergenceGuard:
    def test_appending_onto_a_divergent_log_is_refused(self):
        guard = DivergenceGuard()
        with pytest.raises(Invalid) as caught:
            guard.require_truncation(
                follower_end=1040, leader_epoch_end=1000
            )
        assert "the exact corruption the epoch check prevents" in (
            str(caught.value)
        )

    def test_a_prefix_log_may_append(self):
        guard = DivergenceGuard()
        guard.require_truncation(
            follower_end=900, leader_epoch_end=1000
        )
        assert guard.diverged_past is None

    def test_resolving_the_divergence_restores_appending(self):
        guard = DivergenceGuard()
        with pytest.raises(Invalid):
            guard.require_truncation(1040, 1000)
        verdict = guard.resolve(truncated_to=1000)
        assert "may append again" in verdict

    def test_resolving_to_the_wrong_point_is_refused(self):
        guard = DivergenceGuard()
        with pytest.raises(Invalid):
            guard.require_truncation(1040, 1000)
        with pytest.raises(Invalid) as caught:
            guard.resolve(truncated_to=1010)
        assert "still not a prefix" in str(caught.value)
