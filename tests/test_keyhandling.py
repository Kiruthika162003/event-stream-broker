from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.keyhandling import (
    keys_land_together,
    partition_for_key,
    validate_for_compacted,
)


class TestNullVsEmpty:
    def test_a_null_key_round_robins(self):
        slot, note = partition_for_key(None, 4, round_robin_next=2)
        assert slot == 2
        assert "no per-key order" in note

    def test_an_empty_key_hashes_and_orders(self):
        _, note = partition_for_key(b"", 4, 0)
        assert "a real zero-length key" in note
        # two empty-keyed records land together
        assert keys_land_together(b"", b"", 4)

    def test_a_normal_key_gets_a_stable_home(self):
        slot1, _ = partition_for_key(b"user-7", 8, 0)
        slot2, _ = partition_for_key(b"user-7", 8, 5)
        assert slot1 == slot2

    def test_null_keys_never_land_together(self):
        assert not keys_land_together(None, None, 4)

    def test_zero_partitions_is_refused(self):
        with pytest.raises(Invalid):
            partition_for_key(b"k", 0, 0)


class TestCompactedTopic:
    def test_a_null_key_is_a_category_error(self):
        with pytest.raises(Invalid) as caught:
            validate_for_compacted(None, b"v")
        assert "category error the broker catches" in str(
            caught.value
        )

    def test_a_null_value_is_a_keyed_tombstone(self):
        verdict = validate_for_compacted(b"user-7", None)
        assert "tombstone for key" in verdict
        assert "deletes nothing" in verdict

    def test_a_keyed_record_is_compactable(self):
        assert "compactable record" in validate_for_compacted(
            b"user-7", b"addr"
        )
