from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.varint import (
    decode_varint,
    encode_varint,
    zigzag_decode,
    zigzag_encode,
)


class TestZigzag:
    def test_small_magnitudes_map_to_small_unsigned(self):
        assert zigzag_encode(0) == 0
        assert zigzag_encode(-1) == 1
        assert zigzag_encode(1) == 2
        assert zigzag_encode(-2) == 3

    def test_zigzag_round_trips_across_zero(self):
        for v in range(-1000, 1000):
            assert zigzag_decode(zigzag_encode(v)) == v


class TestVarintRoundTrip:
    def test_it_round_trips_a_range_crossing_zero(self):
        for v in (-1_000_000, -300, -1, 0, 1, 127, 128, 300, 1_000_000):
            data = encode_varint(v)
            decoded, consumed = decode_varint(data)
            assert decoded == v
            assert consumed == len(data)

    def test_a_small_positive_costs_one_byte(self):
        assert len(encode_varint(1)) == 1

    def test_a_small_negative_costs_as_little_as_a_small_positive(self):
        assert len(encode_varint(-1)) == len(encode_varint(1))

    def test_decode_reports_how_many_bytes_it_consumed(self):
        data = encode_varint(300) + b"\xff\xff"
        _, consumed = decode_varint(data)
        assert consumed == len(encode_varint(300))


class TestMalformed:
    def test_a_never_terminating_varint_is_refused(self):
        with pytest.raises(Invalid) as caught:
            decode_varint(b"\x80" * 11)
        assert "did not terminate" in str(caught.value)

    def test_a_truncated_varint_is_refused(self):
        with pytest.raises(Invalid) as caught:
            decode_varint(b"\x80\x80")
        assert "truncated" in str(caught.value)
