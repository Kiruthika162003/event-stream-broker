from __future__ import annotations

import pytest

from relay.bitcask import Bitcask
from relay.errors import Missing


class TestPutGet:
    def test_put_then_get(self):
        b = Bitcask()
        b.put("k", "v1")
        assert b.get("k") == "v1"

    def test_a_later_put_shadows_the_earlier(self):
        b = Bitcask()
        b.put("k", "v1")
        b.put("k", "v2")
        assert b.get("k") == "v2"
        # the old version is still in the log, dead
        assert len(b.log) == 2

    def test_a_missing_key_is_missing(self):
        b = Bitcask()
        with pytest.raises(Missing):
            b.get("k")


class TestDelete:
    def test_delete_writes_a_tombstone_and_removes(self):
        b = Bitcask()
        b.put("k", "v")
        b.delete("k")
        with pytest.raises(Missing):
            b.get("k")

    def test_deleting_an_absent_key_is_refused(self):
        b = Bitcask()
        with pytest.raises(Missing):
            b.delete("k")


class TestCompact:
    def test_compaction_keeps_only_live_values(self):
        b = Bitcask()
        b.put("k", "v1")
        b.put("k", "v2")
        b.put("other", "x")
        b.compact()
        assert len(b.log) == 2
        assert b.get("k") == "v2"
        assert b.get("other") == "x"


class TestDeadRatio:
    def test_it_reports_dead_entries(self):
        b = Bitcask()
        b.put("k", "v1")
        b.put("k", "v2")  # v1 now dead
        note = b.dead_ratio()
        assert "1/2 log entries dead (50%)" in note
