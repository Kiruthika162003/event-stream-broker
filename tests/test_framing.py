from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.framing import FrameReader


def _frame(payload: bytes) -> bytes:
    return len(payload).to_bytes(4, "big") + payload


class TestFeed:
    def test_a_complete_frame_is_yielded(self):
        r = FrameReader(max_size=1000)
        assert r.feed(_frame(b"hello")) == [b"hello"]

    def test_two_frames_in_one_chunk(self):
        r = FrameReader(max_size=1000)
        assert r.feed(_frame(b"ab") + _frame(b"cde")) == [b"ab", b"cde"]

    def test_a_split_frame_buffers_then_yields(self):
        r = FrameReader(max_size=1000)
        whole = _frame(b"hello")
        assert r.feed(whole[:3]) == []
        assert r.feed(whole[3:]) == [b"hello"]

    def test_a_zero_length_frame_is_a_valid_empty_payload(self):
        r = FrameReader(max_size=1000)
        assert r.feed(_frame(b"")) == [b""]

    def test_leftover_bytes_carry_to_the_next_feed(self):
        r = FrameReader(max_size=1000)
        data = _frame(b"one") + b"\x00\x00"  # start of next length
        assert r.feed(data) == [b"one"]
        assert "byte(s) buffered" in r.pending()


class TestHostileLength:
    def test_a_length_over_the_max_is_refused_before_allocating(self):
        r = FrameReader(max_size=10)
        with pytest.raises(Invalid) as caught:
            r.feed((1_000_000).to_bytes(4, "big"))
        assert "before allocating" in str(caught.value)

    def test_a_negative_length_is_refused(self):
        r = FrameReader(max_size=1000)
        with pytest.raises(Invalid) as caught:
            r.feed((-1).to_bytes(4, "big", signed=True))
        assert "negative frame length" in str(caught.value)

    def test_a_bad_max_size_is_refused(self):
        with pytest.raises(Invalid):
            FrameReader(max_size=0)
