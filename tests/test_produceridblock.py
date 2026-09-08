from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.produceridblock import ProducerIdBlock


class TestAllocate:
    def test_ids_come_from_the_block_in_order(self):
        b = ProducerIdBlock(block_start=1000, block_size=3)
        assert b.allocate() == 1000
        assert b.allocate() == 1001
        assert b.allocate() == 1002

    def test_allocating_past_the_block_is_refused(self):
        b = ProducerIdBlock(block_start=1000, block_size=1)
        b.allocate()
        with pytest.raises(Invalid) as caught:
            b.allocate()
        assert "exhausted" in str(caught.value)

    def test_a_zero_size_block_is_refused(self):
        with pytest.raises(Invalid):
            ProducerIdBlock(block_start=0, block_size=0)


class TestRemaining:
    def test_remaining_counts_down(self):
        b = ProducerIdBlock(block_start=0, block_size=5)
        b.allocate()
        b.allocate()
        assert b.remaining() == 3


class TestRefill:
    def test_a_non_overlapping_refill_continues_ids(self):
        b = ProducerIdBlock(block_start=1000, block_size=2)
        b.allocate()
        b.allocate()
        note = b.refill(new_start=2000, new_size=2)
        assert "[2000, 2002)" in note
        assert b.allocate() == 2000

    def test_an_overlapping_refill_is_refused(self):
        b = ProducerIdBlock(block_start=1000, block_size=100)
        with pytest.raises(Invalid) as caught:
            b.refill(new_start=1050, new_size=100)
        assert "break cluster-wide uniqueness" in str(caught.value)


class TestHealth:
    def test_health_reports_remaining(self):
        b = ProducerIdBlock(block_start=0, block_size=10)
        assert "10 id(s) left" in b.health()
