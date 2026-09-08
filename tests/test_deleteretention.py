from __future__ import annotations

import pytest

from relay.deleteretention import DeleteRetention, Tombstone
from relay.errors import Invalid


def tombstone() -> Tombstone:
    return Tombstone(key=b"user-7", offset=500, eligible_at=100)


def retention() -> DeleteRetention:
    return DeleteRetention(retention_ticks=1000)


class TestRemovable:
    def test_aged_and_read_is_removable(self):
        assert retention().removable(
            tombstone(), now=2000, min_consumer_offset=600
        )

    def test_young_is_not_removable(self):
        assert not retention().removable(
            tombstone(), now=200, min_consumer_offset=600
        )

    def test_unread_is_not_removable(self):
        assert not retention().removable(
            tombstone(), now=2000, min_consumer_offset=400
        )

    def test_a_bad_retention_is_refused(self):
        with pytest.raises(Invalid):
            DeleteRetention(retention_ticks=0)


class TestExplain:
    def test_the_clock_binding_says_raise_nothing(self):
        verdict = retention().explain(
            tombstone(), now=200, min_consumer_offset=600
        )
        assert "held on the clock" in verdict
        assert "raise nothing" in verdict

    def test_the_reader_binding_says_find_the_reader(self):
        verdict = retention().explain(
            tombstone(), now=2000, min_consumer_offset=400
        )
        assert "held on a reader" in verdict
        assert "find the stuck reader" in verdict

    def test_both_held_is_named(self):
        verdict = retention().explain(
            tombstone(), now=200, min_consumer_offset=400
        )
        assert "held on both" in verdict

    def test_removable_is_stated(self):
        verdict = retention().explain(
            tombstone(), now=2000, min_consumer_offset=600
        )
        assert "removable" in verdict
