from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.offsetstore import CommitKey, OffsetStore

KEY = CommitKey(group="billing", topic="orders", partition=0)


class TestCommits:
    def test_a_durable_commit_is_stored(self):
        store = OffsetStore()
        verdict = store.commit(KEY, 100, durable=True)
        assert "committed at 100" in verdict
        assert store.fetch(KEY) == 100

    def test_a_non_durable_commit_is_refused(self):
        store = OffsetStore()
        with pytest.raises(Invalid) as caught:
            store.commit(KEY, 100, durable=False)
        assert "replication was meant to survive" in str(
            caught.value
        )

    def test_commits_move_forward(self):
        store = OffsetStore()
        store.commit(KEY, 100, durable=True)
        with pytest.raises(Invalid):
            store.commit(KEY, 50, durable=True)

    def test_an_unknown_key_is_missing(self):
        with pytest.raises(Missing):
            OffsetStore().fetch(KEY)


class TestCompactionBound:
    def test_only_the_latest_commit_per_key_survives(self):
        store = OffsetStore()
        for offset in range(1, 101):
            store.commit(KEY, offset, durable=True)
        assert store.compacted_size() == 1
        assert store.fetch(KEY) == 100

    def test_the_bound_is_group_partition_pairs(self):
        store = OffsetStore()
        for partition in range(3):
            key = CommitKey("g", "t", partition)
            for offset in range(10):
                store.commit(key, offset, durable=True)
        report = store.bound_report()
        assert "30 commit record(s) written, 3 survive" in report
        assert "not by commits ever made" in report
