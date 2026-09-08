from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.lsmtree import LSMTree


class TestPutGet:
    def test_a_write_is_read_from_the_memtable(self):
        t = LSMTree(memtable_limit=10)
        t.put("k", "v")
        assert t.get("k") == "v"

    def test_a_newer_run_shadows_an_older(self):
        t = LSMTree(memtable_limit=1)
        t.put("k", "old")  # flushes (limit 1)
        t.put("k", "new")  # flushes again
        assert t.get("k") == "new"

    def test_a_missing_key_is_missing(self):
        t = LSMTree(memtable_limit=10)
        with pytest.raises(Missing):
            t.get("k")


class TestFlush:
    def test_flush_moves_the_memtable_to_a_run(self):
        t = LSMTree(memtable_limit=10)
        t.put("k", "v")
        t.flush()
        assert len(t.runs) == 1
        assert t.memtable == {}

    def test_flushing_an_empty_memtable_is_refused(self):
        t = LSMTree(memtable_limit=10)
        with pytest.raises(Invalid):
            t.flush()


class TestDeleteAndCompact:
    def test_a_delete_tombstones(self):
        t = LSMTree(memtable_limit=10)
        t.put("k", "v")
        t.delete("k")
        with pytest.raises(Missing):
            t.get("k")

    def test_compaction_merges_runs_and_drops_tombstones(self):
        t = LSMTree(memtable_limit=1)
        t.put("a", "1")
        t.put("b", "2")
        t.put("a", "3")
        t.compact()
        assert len(t.runs) == 1
        assert t.get("a") == "3"
        assert t.get("b") == "2"


class TestFanout:
    def test_fanout_reports_run_count(self):
        t = LSMTree(memtable_limit=1)
        t.put("a", "1")
        t.put("b", "2")
        assert "2 run(s)" in t.read_fanout()
