from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.wireschema import SchemaEnvelope


def _env():
    return SchemaEnvelope(known_ids={1, 2, 42})


class TestRoundTrip:
    def test_encode_then_decode_recovers_id_and_payload(self):
        env = _env()
        data = env.encode(42, b"hello")
        schema_id, payload = env.decode(data)
        assert schema_id == 42
        assert payload == b"hello"

    def test_the_prefix_is_five_bytes(self):
        env = _env()
        assert len(env.encode(1, b"")) == 5


class TestDecodeFaults:
    def test_a_short_buffer_is_refused(self):
        with pytest.raises(Invalid) as caught:
            _env().decode(b"\x00\x00")
        assert "too short" in str(caught.value)

    def test_an_unknown_magic_byte_is_refused(self):
        # magic byte 7 instead of 0
        data = bytes([7]) + (42).to_bytes(4, "big") + b"x"
        with pytest.raises(Invalid) as caught:
            _env().decode(data)
        assert "unknown magic byte 7" in str(caught.value)

    def test_an_unregistered_schema_id_is_refused(self):
        env = _env()
        data = env.encode(999, b"x")
        with pytest.raises(Invalid) as caught:
            env.decode(data)
        assert "not registered" in str(caught.value)

    def test_an_oversized_schema_id_is_refused_on_encode(self):
        with pytest.raises(Invalid):
            _env().encode(0x1_0000_0000, b"x")


class TestDescribe:
    def test_describe_names_id_and_length(self):
        env = _env()
        note = env.describe(env.encode(2, b"abcd"))
        assert "schema id 2, payload 4 byte(s)" in note
