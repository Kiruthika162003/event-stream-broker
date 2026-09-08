"""Wire schema: each record carries the id of the schema that decodes it.

When records on a topic share an evolving schema, a consumer
reading a record needs to know which version of the schema wrote
it, and embedding the whole schema in every record would be
enormous, so instead each record carries a small schema id and the
consumer looks the schema up by that id. The wire format is a
prefix: a magic byte marking the format, then a four-byte schema
id, then the serialized payload. The deserializer reads the magic
byte first and rejects a record whose magic it does not recognize,
because a record not written in this format cannot be decoded by
assuming it was, and guessing would turn arbitrary bytes into a
bogus schema id. It then reads the schema id, fetches that schema,
and decodes the payload against it, so the same topic can hold
records written by producers on different schema versions and each
is decoded by the schema that actually wrote it. This is what lets
schema evolution work at all: an old record keeps its old schema
id and is still decodable after the schema evolved, because its id
still resolves to the schema it was written with. The parser
refuses a buffer too short to hold the prefix, which cannot carry a
schema id and is either truncated or not a schema-framed record,
and refuses a schema id the registry does not know, a record
referencing a schema that was never registered or was deleted. It
reports the schema id and payload length, because a topic suddenly
carrying a new schema id is a producer that deployed a schema
change, visible in the ids before it shows up as a consumer
failing to decode a field it did not expect.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

_MAGIC = 0
_PREFIX = 5  # 1 magic byte + 4 schema id bytes


@dataclass
class SchemaEnvelope:
    known_ids: set[int] = field(default_factory=set)

    def encode(self, schema_id: int, payload: bytes) -> bytes:
        if schema_id < 0 or schema_id > 0xFFFFFFFF:
            raise Invalid("schema id must fit in four bytes")
        return bytes([_MAGIC]) + schema_id.to_bytes(4, "big") + payload

    def decode(self, data: bytes) -> tuple[int, bytes]:
        if len(data) < _PREFIX:
            raise Invalid(
                "buffer too short for the schema prefix; truncated or not "
                "a schema-framed record"
            )
        if data[0] != _MAGIC:
            raise Invalid(
                f"unknown magic byte {data[0]}; a record not in this "
                "format, decoding it would turn arbitrary bytes into a "
                "bogus schema id"
            )
        schema_id = int.from_bytes(data[1:5], "big")
        if schema_id not in self.known_ids:
            raise Invalid(
                f"schema id {schema_id} is not registered; the record "
                "references a schema never registered or deleted"
            )
        return schema_id, data[_PREFIX:]

    def describe(self, data: bytes) -> str:
        schema_id, payload = self.decode(data)
        return (
            f"schema id {schema_id}, payload {len(payload)} byte(s); a new "
            "id appearing is a producer that deployed a schema change"
        )
