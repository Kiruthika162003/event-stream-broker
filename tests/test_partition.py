from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.partition import Partition
from relay.records import Record


def loaded_partition(appended: int = 5, committed: int = 3) -> Partition:
    partition = Partition(number=0)
    for number in range(appended):
        partition.append(Record(value=f"e{number}".encode()))
    partition.advance_watermark(committed)
    return partition


class TestTheWatermark:
    def test_advancing_names_the_committed_range(self):
        partition = loaded_partition()
        assert partition.advance_watermark(5) == (
            "partition 0 committed through 4"
        )

    def test_the_watermark_never_retreats(self):
        partition = loaded_partition()
        with pytest.raises(Invalid) as caught:
            partition.advance_watermark(1)
        assert "un-promises delivered records" in str(
            caught.value
        )

    def test_the_watermark_cannot_pass_the_end(self):
        partition = loaded_partition()
        with pytest.raises(Invalid) as caught:
            partition.advance_watermark(99)
        assert "a bookkeeping lie" in str(caught.value)


class TestConsuming:
    def test_committed_records_are_served(self):
        partition = loaded_partition()
        assert partition.consume(2).value == b"e2"

    def test_the_uncommitted_record_could_unhappen(self):
        partition = loaded_partition()
        with pytest.raises(Missing) as caught:
            partition.consume(3)
        assert "wears the consumer's name" in str(caught.value)

    def test_the_honesty_interval_counts_the_gap(self):
        assert loaded_partition().honesty_interval() == (
            "partition 0: 2 record(s) exist but are not yet "
            "promises"
        )


class TestLag:
    def test_lag_measures_against_the_watermark(self):
        assert loaded_partition().lag_of(1) == 2

    def test_a_consumer_ahead_of_the_watermark_is_impossible(self):
        with pytest.raises(Invalid):
            loaded_partition().lag_of(4)
