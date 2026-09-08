from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.quorumread import QuorumConfig


class TestConsistency:
    def test_overlapping_quorums_are_consistent(self):
        # N=3, R=2, W=2 -> R+W=4 > 3
        assert QuorumConfig(replicas=3, read_quorum=2, write_quorum=2).is_consistent()

    def test_disjoint_quorums_can_be_stale(self):
        # N=3, R=1, W=1 -> R+W=2 <= 3
        assert not QuorumConfig(replicas=3, read_quorum=1, write_quorum=1).is_consistent()

    def test_write_all_read_one_is_consistent(self):
        assert QuorumConfig(replicas=3, read_quorum=1, write_quorum=3).is_consistent()


class TestFailures:
    def test_it_reports_failures_tolerated_per_side(self):
        q = QuorumConfig(replicas=5, read_quorum=3, write_quorum=3)
        assert q.write_failures_tolerated() == 2
        assert q.read_failures_tolerated() == 2


class TestRefusals:
    def test_a_quorum_above_n_is_refused(self):
        with pytest.raises(Invalid):
            QuorumConfig(replicas=3, read_quorum=4, write_quorum=2)

    def test_a_zero_quorum_is_refused(self):
        with pytest.raises(Invalid):
            QuorumConfig(replicas=3, read_quorum=0, write_quorum=2)


class TestReport:
    def test_a_consistent_config_is_named(self):
        note = QuorumConfig(replicas=3, read_quorum=2, write_quorum=2).report()
        assert "consistent" in note
        assert "R+W > N" in note

    def test_a_stale_possible_config_is_named(self):
        note = QuorumConfig(replicas=3, read_quorum=1, write_quorum=1).report()
        assert "STALE-POSSIBLE" in note
