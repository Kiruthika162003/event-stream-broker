from __future__ import annotations

import pytest

from relay.consumergroup import ConsumerGroup, GroupRegistry
from relay.errors import Invalid, Missing
from relay.partition import Partition
from relay.records import Record


def partition_with(committed: int = 5) -> Partition:
    partition = Partition(number=2)
    for number in range(committed + 2):
        partition.append(Record(value=f"e{number}".encode()))
    partition.advance_watermark(committed)
    return partition


def group() -> ConsumerGroup:
    return ConsumerGroup(
        name="billing", contract="at-least-once"
    )


class TestTheContract:
    def test_a_group_must_sign_one(self):
        with pytest.raises(Invalid) as caught:
            ConsumerGroup(name="x", contract="exactly-vibes")
        assert "never knew they had chosen" in str(caught.value)

    def test_each_contract_states_its_crash_behavior(self):
        assert "a crash replays" in group().contract_line()
        cautious = ConsumerGroup(
            name="metrics", contract="at-most-once"
        )
        assert "a crash loses" in cautious.contract_line()


class TestCommits:
    def test_commits_move_forward_only(self):
        chosen = group()
        partition = partition_with()
        chosen.commit(partition, 3)
        with pytest.raises(Invalid) as caught:
            chosen.commit(partition, 1)
        assert "commits move forward" in str(caught.value)

    def test_committing_past_the_watermark_is_stolen_credit(self):
        with pytest.raises(Invalid) as caught:
            group().commit(partition_with(), 7)
        assert "claiming credit" in str(caught.value)

    def test_skips_are_logged_not_disguised(self):
        chosen = group()
        verdict = chosen.commit(partition_with(), 4)
        assert "3 skip(s) logged, not disguised" in verdict
        assert chosen.skips_logged == [
            "partition 2: skipped 3 record(s) between 0 and 3"
        ]


class TestLag:
    def test_lag_uses_the_watermark_as_denominator(self):
        chosen = group()
        partition = partition_with(committed=5)
        chosen.commit(partition, 2)
        assert chosen.lag(partition) == 3

    def test_a_fresh_group_lags_the_whole_window(self):
        assert group().lag(partition_with(committed=5)) == 5


class TestTheRegistry:
    def test_registration_is_once(self):
        registry = GroupRegistry()
        registry.register("billing", "at-least-once")
        with pytest.raises(Invalid):
            registry.register("billing", "at-most-once")

    def test_a_missing_group_is_missing(self):
        with pytest.raises(Missing):
            GroupRegistry().get("ghost")
