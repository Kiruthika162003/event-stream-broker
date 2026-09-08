from __future__ import annotations

import pytest

from relay.batchvalidate import Batch, validate_batch
from relay.errors import Invalid


def good() -> Batch:
    return Batch(
        magic=2,
        crc=12345,
        computed_crc=12345,
        base_offset=1000,
        last_offset_delta=4,
        record_count=5,
    )


class TestValid:
    def test_a_clean_batch_validates(self):
        verdict = validate_batch(good())
        assert "batch of 5 record(s) valid at base 1000" in verdict


class TestChecksOrdered:
    def test_a_wrong_magic_fails_first(self):
        batch = Batch(
            magic=1, crc=1, computed_crc=2,
            base_offset=0, last_offset_delta=4, record_count=5,
        )
        with pytest.raises(Invalid) as caught:
            validate_batch(batch)
        assert "fix the serializer" in str(caught.value)

    def test_a_crc_mismatch_is_corruption_at_the_door(self):
        batch = Batch(
            magic=2, crc=1, computed_crc=2,
            base_offset=0, last_offset_delta=4, record_count=5,
        )
        with pytest.raises(Invalid) as caught:
            validate_batch(batch)
        assert "one suspect, the wire" in str(caught.value)

    def test_an_empty_batch_is_a_client_bug(self):
        batch = Batch(
            magic=2, crc=1, computed_crc=1,
            base_offset=0, last_offset_delta=0, record_count=0,
        )
        with pytest.raises(Invalid) as caught:
            validate_batch(batch)
        assert "produced nothing" in str(caught.value)

    def test_offset_inconsistency_is_caught(self):
        batch = Batch(
            magic=2, crc=1, computed_crc=1,
            base_offset=0, last_offset_delta=9, record_count=5,
        )
        with pytest.raises(Invalid) as caught:
            validate_batch(batch)
        assert "desyncs every offset after it" in str(caught.value)
