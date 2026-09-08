from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.tablejoin import TableJoin


def _join():
    return TableJoin(left_partitions=4, right_partitions=4)


class TestCoPartition:
    def test_mismatched_partitions_are_refused(self):
        with pytest.raises(Invalid):
            TableJoin(left_partitions=4, right_partitions=8)


class TestJoin:
    def test_both_sides_present_emits_a_result(self):
        j = _join()
        j.update_left("k", 10)
        assert "k: joined = 30" in j.update_right("k", 20)

    def test_one_side_absent_emits_nothing_to_withdraw(self):
        j = _join()
        note = j.update_left("k", 10)
        assert "nothing to withdraw" in note

    def test_an_update_re_emits_the_join(self):
        j = _join()
        j.update_left("k", 10)
        j.update_right("k", 20)
        assert "k: joined = 25" in j.update_left("k", 5)


class TestTombstone:
    def test_a_tombstone_withdraws_a_previous_join(self):
        j = _join()
        j.update_left("k", 10)
        j.update_right("k", 20)
        note = j.update_right("k", None)
        assert "withdrawing the previous join" in note

    def test_a_tombstone_for_a_never_joined_key_withdraws_nothing(self):
        j = _join()
        j.update_left("k", 10)  # right never set
        note = j.update_left("k", None)
        assert "nothing to withdraw" in note


class TestJoinable:
    def test_it_counts_joinable_against_half_present(self):
        j = _join()
        j.update_left("a", 1)
        j.update_right("a", 2)
        j.update_left("b", 3)
        note = j.joinable()
        assert "1 key(s) joinable, 1 half-present" in note
