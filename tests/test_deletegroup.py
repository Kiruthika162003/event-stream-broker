from __future__ import annotations

import pytest

from relay.deletegroup import GroupRegistry
from relay.errors import Invalid, Missing


class TestDelete:
    def test_an_empty_group_is_deleted_with_its_offsets(self):
        reg = GroupRegistry(
            members={"g": 0},
            offset_partitions={"g": 12},
        )
        note = reg.delete("g")
        assert "discarding offsets for 12 partition(s)" in note
        assert "g" in reg.deleted

    def test_a_group_with_live_members_is_refused(self):
        reg = GroupRegistry(members={"g": 3})
        with pytest.raises(Invalid) as caught:
            reg.delete("g")
        assert "3 live member(s)" in str(caught.value)

    def test_an_unknown_group_is_missing(self):
        reg = GroupRegistry()
        with pytest.raises(Missing):
            reg.delete("nope")

    def test_a_second_delete_is_refused(self):
        reg = GroupRegistry(members={"g": 0}, offset_partitions={"g": 1})
        reg.delete("g")
        with pytest.raises(Invalid) as caught:
            reg.delete("g")
        assert "already deleted" in str(caught.value)
