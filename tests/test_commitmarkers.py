from __future__ import annotations

import pytest

from relay.commitmarkers import CommitMarkers
from relay.errors import Invalid


def _m():
    return CommitMarkers(partitions={"t-0", "t-1", "t-2"})


class TestWrite:
    def test_markers_accumulate_toward_commit(self):
        m = _m()
        assert "1/3" in m.write_marker("t-0")
        assert "2/3" in m.write_marker("t-1")

    def test_a_marker_to_an_unwritten_partition_is_refused(self):
        m = _m()
        with pytest.raises(Invalid) as caught:
            m.write_marker("t-9")
        assert "spurious marker" in str(caught.value)

    def test_a_transaction_with_no_partitions_is_refused(self):
        with pytest.raises(Invalid):
            CommitMarkers(partitions=set())


class TestCommit:
    def test_committed_only_when_all_markers_written(self):
        m = _m()
        m.write_marker("t-0")
        m.write_marker("t-1")
        assert not m.is_committed()
        m.write_marker("t-2")
        assert m.is_committed()
        assert "all 3 partition(s)" in m.declare_committed()

    def test_declaring_committed_early_is_refused(self):
        m = _m()
        m.write_marker("t-0")
        with pytest.raises(Invalid) as caught:
            m.declare_committed()
        assert "half-committed state" in str(caught.value)


class TestRecover:
    def test_recovery_re_drives_outstanding_markers(self):
        m = _m()
        m.write_marker("t-0")
        note = m.recover()
        assert "re-driving 2 outstanding marker(s)" in note

    def test_nothing_to_recover_when_all_written(self):
        m = _m()
        for p in ("t-0", "t-1", "t-2"):
            m.write_marker(p)
        assert "nothing to recover" in m.recover()
