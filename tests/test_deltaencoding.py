from __future__ import annotations

import pytest

from relay.deltaencoding import compression_note, decode, encode
from relay.errors import Invalid


class TestRoundTrip:
    def test_encode_then_decode_recovers_the_values(self):
        values = [1000, 1003, 1005, 1010, 1050]
        assert decode(encode(values)) == values

    def test_the_first_value_is_the_base(self):
        assert encode([1000, 1003, 1005]) == [1000, 3, 2]

    def test_an_empty_sequence_round_trips(self):
        assert encode([]) == []
        assert decode([]) == []

    def test_a_single_value_is_just_the_base(self):
        assert encode([42]) == [42]
        assert decode([42]) == [42]


class TestSorted:
    def test_a_non_increasing_input_is_refused(self):
        with pytest.raises(Invalid) as caught:
            encode([1000, 1005, 1002])
        assert "not sorted" in str(caught.value)

    def test_equal_adjacent_values_are_allowed(self):
        # a zero delta is fine; only negative is refused
        assert encode([5, 5, 7]) == [5, 0, 2]


class TestCompression:
    def test_close_values_compress(self):
        note = compression_note([100000, 100001, 100002, 100003])
        assert "saved" in note

    def test_an_empty_sequence_notes_nothing(self):
        assert "nothing to encode" in compression_note([])
