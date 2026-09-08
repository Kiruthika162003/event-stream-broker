from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.ringbuffer import RingBuffer


class TestAppend:
    def test_it_holds_up_to_capacity_in_order(self):
        b = RingBuffer(capacity=3)
        b.append(1)
        b.append(2)
        b.append(3)
        assert b.contents() == [1, 2, 3]
        assert not b.has_wrapped()

    def test_appending_past_capacity_overwrites_the_oldest(self):
        b = RingBuffer(capacity=3)
        for v in (1, 2, 3, 4):
            b.append(v)
        assert b.contents() == [2, 3, 4]
        assert b.has_wrapped()

    def test_a_full_wrap_keeps_the_last_capacity_in_order(self):
        b = RingBuffer(capacity=3)
        for v in (1, 2, 3, 4, 5, 6, 7):
            b.append(v)
        assert b.contents() == [5, 6, 7]

    def test_size_caps_at_capacity(self):
        b = RingBuffer(capacity=2)
        for v in (1, 2, 3):
            b.append(v)
        assert b.size() == 2


class TestConfig:
    def test_a_zero_capacity_is_refused(self):
        with pytest.raises(Invalid):
            RingBuffer(capacity=0)


class TestFillNote:
    def test_a_young_buffer_warns_about_fewer_samples(self):
        b = RingBuffer(capacity=10)
        b.append(1)
        assert "not yet wrapped" in b.fill_note()

    def test_a_full_buffer_reports_overwriting(self):
        b = RingBuffer(capacity=2)
        for v in (1, 2, 3):
            b.append(v)
        assert "overwriting the oldest" in b.fill_note()
