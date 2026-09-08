from __future__ import annotations

import pytest

from relay.crc32c import crc32c
from relay.errors import Invalid
from relay.readverify import ReadVerifier


class TestServe:
    def test_a_good_batch_verifies_on_read(self):
        v = ReadVerifier()
        data = b"payload"
        assert "served" in v.serve(data, crc32c(data))

    def test_a_rotted_batch_is_refused(self):
        v = ReadVerifier()
        data = b"payload"
        good = crc32c(data)
        rotted = bytearray(data)
        rotted[0] ^= 0x01  # a bit flipped on disk
        with pytest.raises(Invalid) as caught:
            v.serve(bytes(rotted), good)
        assert "rotted on disk" in str(caught.value)


class TestRepair:
    def test_repair_from_a_good_replica(self):
        v = ReadVerifier()
        data = b"payload"
        assert v.repair_from(data, crc32c(data)) == data

    def test_repair_from_a_corrupt_replica_is_refused(self):
        v = ReadVerifier()
        data = b"payload"
        good = crc32c(data)
        bad = bytearray(data)
        bad[0] ^= 0x01
        with pytest.raises(Invalid) as caught:
            v.repair_from(bytes(bad), good)
        assert "corruption over corruption" in str(caught.value)


class TestFailureRate:
    def test_it_tracks_the_failure_rate(self):
        v = ReadVerifier()
        data = b"payload"
        good = crc32c(data)
        v.serve(data, good)
        rotted = bytearray(data)
        rotted[0] ^= 0x01
        with pytest.raises(Invalid):
            v.serve(bytes(rotted), good)
        note = v.failure_rate()
        assert "1/2 reads failed verification" in note
