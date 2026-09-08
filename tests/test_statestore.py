from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.statestore import StateStore


class TestRestore:
    def test_the_store_is_ready_once_caught_up(self):
        store = StateStore(changelog_end=3)
        store.apply_changelog(0, "a", 1)
        store.apply_changelog(1, "b", 2)
        store.apply_changelog(2, "a", 5)
        assert store.ready
        assert store.read("a") == 5

    def test_reads_before_restore_are_refused(self):
        store = StateStore(changelog_end=3)
        store.apply_changelog(0, "a", 1)
        with pytest.raises(Invalid) as caught:
            store.read("a")
        assert "unread tail" in str(caught.value)

    def test_an_out_of_order_changelog_record_is_refused(self):
        store = StateStore(changelog_end=3)
        store.apply_changelog(1, "a", 1)
        with pytest.raises(Invalid) as caught:
            store.apply_changelog(0, "b", 2)
        assert "out of order" in str(caught.value)


class TestWrite:
    def test_a_write_requires_the_changelog_ack(self):
        store = StateStore(changelog_end=0)
        store.ready = True
        with pytest.raises(Invalid) as caught:
            store.write("a", 1, changelog_acked=False)
        assert "not acknowledged" in str(caught.value)

    def test_an_acked_write_is_durable(self):
        store = StateStore(changelog_end=0)
        store.ready = True
        note = store.write("a", 1, changelog_acked=True)
        assert "durable" in note
        assert store.read("a") == 1


class TestProgress:
    def test_progress_is_reported(self):
        store = StateStore(changelog_end=100)
        store.apply_changelog(0, "a", 1)
        assert "restored 1/100" in store.restore_progress()
