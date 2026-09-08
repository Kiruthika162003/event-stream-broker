from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.prefixcompression import compression_note, decode, encode


class TestRoundTrip:
    def test_shared_prefixes_are_factored_out(self):
        keys = ["orders-2024-01", "orders-2024-02", "orders-2024-03"]
        entries = encode(keys)
        assert entries[0] == (0, "orders-2024-01")
        assert entries[1] == (13, "2")
        assert decode(entries) == keys

    def test_an_empty_list_round_trips(self):
        assert encode([]) == []
        assert decode([]) == []

    def test_unrelated_keys_share_nothing(self):
        keys = ["apple", "banana", "cherry"]
        entries = encode(keys)
        assert all(shared == 0 for shared, _ in entries)
        assert decode(entries) == keys


class TestSorted:
    def test_unsorted_input_is_refused(self):
        with pytest.raises(Invalid) as caught:
            encode(["b", "a"])
        assert "not sorted" in str(caught.value)


class TestDecodeFaults:
    def test_a_shared_length_past_the_previous_key_is_refused(self):
        with pytest.raises(Invalid) as caught:
            decode([(0, "ab"), (5, "x")])
        assert "corruption" in str(caught.value)


class TestCompression:
    def test_clustered_keys_compress(self):
        note = compression_note(["orders-a", "orders-b", "orders-c"])
        assert "saved" in note

    def test_no_keys_notes_nothing(self):
        assert "nothing to encode" in compression_note([])
