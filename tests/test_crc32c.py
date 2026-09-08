from __future__ import annotations

import pytest

from relay.crc32c import check_batch, crc32c, verify
from relay.errors import Invalid


class TestKnownVectors:
    def test_the_standard_check_vector(self):
        # The canonical CRC-32C check value for "123456789".
        assert crc32c(b"123456789") == 0xE3069283

    def test_the_empty_input_is_zero(self):
        assert crc32c(b"") == 0x00000000

    def test_a_single_byte_is_stable(self):
        first = crc32c(b"a")
        assert first == crc32c(b"a")


class TestVerify:
    def test_a_matching_crc_verifies(self):
        data = b"the quick brown fox"
        assert verify(data, crc32c(data))

    def test_a_single_bit_flip_is_caught(self):
        data = bytearray(b"the quick brown fox")
        good = crc32c(bytes(data))
        data[0] ^= 0x01
        assert not verify(bytes(data), good)

    def test_a_non_32_bit_stored_crc_is_refused(self):
        with pytest.raises(Invalid) as caught:
            verify(b"x", 0x1_0000_0000)
        assert "overflowed its width" in str(caught.value)


class TestCheckBatch:
    def test_a_good_batch_reports_its_crc(self):
        data = b"payload"
        note = check_batch(data, crc32c(data))
        assert "batch verified" in note

    def test_a_corrupt_batch_is_refused(self):
        with pytest.raises(Invalid) as caught:
            check_batch(b"payload", 0xDEADBEEF)
        assert "must be refused, not appended" in str(caught.value)
