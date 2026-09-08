from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.tablestreamduality import TableStream


class TestFold:
    def test_folding_keeps_the_latest_per_key(self):
        ts = TableStream()
        ts.fold("a", 1)
        ts.fold("a", 5)
        ts.fold("b", 2)
        assert ts.table == {"a": 5, "b": 2}

    def test_a_tombstone_deletes_the_key(self):
        ts = TableStream()
        ts.fold("a", 1)
        ts.fold("a", None)
        assert "a" not in ts.table

    def test_a_tombstone_leaves_no_phantom_key(self):
        ts = TableStream()
        ts.fold("a", None)  # delete a key that was never set
        assert ts.table == {}

    def test_an_unkeyed_update_is_refused(self):
        ts = TableStream()
        with pytest.raises(Invalid):
            ts.fold("", 1)


class TestChangelog:
    def test_the_changelog_reconstructs_the_table(self):
        ts = TableStream()
        ts.fold("a", 1)
        ts.fold("b", 2)
        assert ts.changelog() == [("a", 1), ("b", 2)]


class TestCompaction:
    def test_the_ratio_reflects_updates_per_key(self):
        ts = TableStream()
        for v in range(10):
            ts.fold("a", v)
        note = ts.compaction_ratio()
        assert "10 update(s) folded into 1 key(s)" in note
        assert "10.0x compaction" in note

    def test_an_empty_stream_folds_nothing(self):
        assert "nothing folded" in TableStream().compaction_ratio()
