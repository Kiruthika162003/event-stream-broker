from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.snapshotisolation import SnapshotIsolation


class TestReads:
    def test_a_read_sees_the_snapshot_at_start(self):
        si = SnapshotIsolation()
        start = si.begin()
        assert f"version {start}" in si.read("k", start)

    def test_a_read_ignores_commits_after_its_start(self):
        si = SnapshotIsolation()
        early = si.begin()
        si.commit(si.begin(), {"k"})  # someone commits k after early's start
        note = si.read("k", early)
        assert "ignoring later commits" in note


class TestCommit:
    def test_a_clean_commit_advances_the_version(self):
        si = SnapshotIsolation()
        start = si.begin()
        assert "version 1" in si.commit(start, {"a", "b"})

    def test_two_disjoint_commits_both_succeed(self):
        si = SnapshotIsolation()
        s1 = si.begin()
        si.commit(s1, {"a"})
        s2 = si.begin()
        assert "version 2" in si.commit(s2, {"b"})

    def test_a_write_write_conflict_aborts_the_later_committer(self):
        si = SnapshotIsolation()
        # both transactions start at the same version
        t1 = si.begin()
        t2 = si.begin()
        si.commit(t1, {"shared"})  # first committer wins
        with pytest.raises(Invalid) as caught:
            si.commit(t2, {"shared"})
        assert "first-committer-wins" in str(caught.value)

    def test_a_lost_update_cannot_happen(self):
        # two transactions read the same key, both write it; the second aborts
        si = SnapshotIsolation()
        a = si.begin()
        b = si.begin()
        si.read("balance", a)
        si.read("balance", b)
        si.commit(a, {"balance"})
        with pytest.raises(Invalid):
            si.commit(b, {"balance"})


class TestWriteSkew:
    def test_the_write_skew_limit_is_named(self):
        assert "write skew" in SnapshotIsolation().write_skew_note()

    def test_write_skew_slips_through(self):
        # two transactions read overlapping keys but write disjoint keys;
        # snapshot isolation detects no conflict, the honest gap
        si = SnapshotIsolation()
        t1 = si.begin()
        t2 = si.begin()
        si.read("on_call_a", t1)
        si.read("on_call_b", t1)
        si.read("on_call_a", t2)
        si.read("on_call_b", t2)
        si.commit(t1, {"on_call_a"})  # t1 takes a off call
        # t2 wrote a different key, so no write-write conflict is raised
        assert "version 2" in si.commit(t2, {"on_call_b"})
