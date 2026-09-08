from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.snapshotinstall import REPLAY, SNAPSHOT, SnapshotInstaller


class TestMechanism:
    def test_a_follower_within_the_log_replays(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=500)
        assert s.mechanism() == REPLAY

    def test_a_follower_before_the_log_start_needs_a_snapshot(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=50)
        assert s.mechanism() == SNAPSHOT


class TestInstall:
    def test_install_advances_the_follower(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=50)
        assert "installed at 100" in s.install(100)
        assert s.follower_position == 100

    def test_a_backwards_snapshot_is_refused(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=500)
        with pytest.raises(Invalid) as caught:
            s.install(400)
        assert "move the follower backwards" in str(caught.value)

    def test_a_snapshot_past_the_log_end_is_refused(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=50)
        with pytest.raises(Invalid) as caught:
            s.install(2000)
        assert "does not exist" in str(caught.value)


class TestReport:
    def test_a_far_behind_follower_reports_snapshot(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=20)
        note = s.report()
        assert "compacted away" in note
        assert "retention is too short" in note

    def test_a_caught_up_follower_reports_replay(self):
        s = SnapshotInstaller(log_start=100, log_end=1000, follower_position=900)
        assert "replay the 100 missing" in s.report()
