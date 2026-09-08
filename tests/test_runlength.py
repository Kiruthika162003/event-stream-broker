from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.runlength import compression_note, decode, encode


class TestRoundTrip:
    def test_runs_encode_to_value_count_pairs(self):
        assert encode([1, 1, 1, 2, 2, 3]) == [(1, 3), (2, 2), (3, 1)]

    def test_decode_expands_the_runs(self):
        assert decode([(1, 3), (2, 2), (3, 1)]) == [1, 1, 1, 2, 2, 3]

    def test_an_empty_sequence_round_trips(self):
        assert encode([]) == []
        assert decode([]) == []

    def test_a_single_value_is_one_run(self):
        assert encode([9]) == [(9, 1)]


class TestDecodeFaults:
    def test_a_non_positive_count_is_refused(self):
        with pytest.raises(Invalid) as caught:
            decode([(1, 0)])
        assert "cannot describe a run" in str(caught.value)


class TestCompression:
    def test_runny_data_compresses(self):
        note = compression_note([1, 1, 1, 1, 1, 2, 2, 2])
        assert "saved" in note
        assert "earns its place" in note

    def test_random_data_does_not_compress(self):
        note = compression_note([1, 2, 3, 4, 5])
        assert "no saving" in note
        assert "should not have been applied" in note
