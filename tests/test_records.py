from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.records import MAX_VALUE_BYTES, Record


class TestConstruction:
    def test_a_record_checksums_itself_at_birth(self):
        record = Record(value=b"order-created")
        assert len(record.checksum) == 16
        record.verify()

    def test_the_key_and_headers_are_inside_the_checksum(self):
        plain = Record(value=b"v")
        keyed = Record(value=b"v", key=b"user-7")
        headed = Record(
            value=b"v", headers=(("source", "billing"),)
        )
        assert len(
            {plain.checksum, keyed.checksum, headed.checksum}
        ) == 3

    def test_an_empty_value_is_a_heartbeat(self):
        with pytest.raises(Invalid) as caught:
            Record(value=b"")
        assert "heartbeats have their own channel" in str(
            caught.value
        )

    def test_the_oversized_value_ships_a_pointer(self):
        with pytest.raises(Invalid) as caught:
            Record(value=b"x" * (MAX_VALUE_BYTES + 1))
        assert "ship a pointer, not the payload" in str(
            caught.value
        )

    def test_nameless_headers_are_refused(self):
        with pytest.raises(Invalid):
            Record(value=b"v", headers=((" ", "x"),))


class TestIntegrity:
    def test_size_counts_every_part(self):
        record = Record(
            value=b"12345",
            key=b"abc",
            headers=(("k", "vv"),),
        )
        assert record.size_bytes() == 5 + 3 + 1 + 2

    def test_identical_bodies_share_a_checksum(self):
        assert Record(value=b"v", key=b"k").checksum == (
            Record(value=b"v", key=b"k").checksum
        )
