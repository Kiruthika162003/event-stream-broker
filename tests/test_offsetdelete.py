from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.offsetdelete import OffsetDeleter


class TestDelete:
    def test_an_unowned_offset_is_deleted(self):
        d = OffsetDeleter(committed={"t-0": 100})
        assert "offset deleted" in d.delete("t-0")
        assert "t-0" not in d.committed

    def test_an_owned_partition_is_refused(self):
        d = OffsetDeleter(committed={"t-0": 100}, owned={"t-0"})
        with pytest.raises(Invalid) as caught:
            d.delete("t-0")
        assert "owned by a live member" in str(caught.value)

    def test_a_partition_with_no_offset_is_a_no_op(self):
        d = OffsetDeleter()
        assert "nothing to delete" in d.delete("t-9")


class TestDeleteMany:
    def test_it_counts_deleted_skipped_and_refused(self):
        d = OffsetDeleter(
            committed={"t-0": 1, "t-1": 2, "t-2": 3},
            owned={"t-2"},
        )
        note = d.delete_many(["t-0", "t-1", "t-2", "t-9"])
        assert "2 deleted" in note
        assert "1 already empty" in note
        assert "1 refused" in note
