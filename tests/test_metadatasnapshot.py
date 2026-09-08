from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.metadatasnapshot import SnapshotManager


class TestTake:
    def test_a_snapshot_records_its_offset(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        assert "at 500" in m.take(500)
        assert m.snapshot_offset == 500

    def test_a_snapshot_past_the_log_end_is_refused(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        with pytest.raises(Invalid):
            m.take(2000)

    def test_a_snapshot_must_advance(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(500)
        with pytest.raises(Invalid) as caught:
            m.take(400)
        assert "must advance" in str(caught.value)


class TestDiscard:
    def test_discard_requires_a_durable_snapshot(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(500)
        with pytest.raises(Invalid) as caught:
            m.discard_below()
        assert "not yet durably written" in str(caught.value)

    def test_a_durable_snapshot_lets_the_log_start_advance(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(500)
        m.mark_durable()
        m.discard_below()
        assert m.log_start == 501


class TestReplayTail:
    def test_the_tail_is_what_changed_since_the_snapshot(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(700)
        assert m.replay_tail() == 300

    def test_without_a_snapshot_the_whole_log_replays(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        assert m.replay_tail() == 1000


class TestLoad:
    def test_load_reports_the_tail_length(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(900)
        assert "tail of 100 record(s)" in m.load()

    def test_a_log_start_past_the_snapshot_is_a_hole(self):
        m = SnapshotManager(log_start=0, log_end=1000)
        m.take(500)
        m.mark_durable()
        m.discard_below()
        m.log_start = 800
        with pytest.raises(Invalid) as caught:
            m.load()
        assert "would have a hole" in str(caught.value)
