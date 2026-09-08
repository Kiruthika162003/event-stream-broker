"""Schema resolution: read old data with a new schema by filling and dropping.

A record is written with the schema the producer had at the time,
the writer schema, and read with the schema the consumer has now,
the reader schema, and when those differ the reader must resolve
the difference field by field rather than fail. Three cases cover
it. A field present in both is read straight across when the types
match. A field the reader has but the writer did not, added since
the record was written, is filled from the reader's default,
because the old record simply has no value for it and the default
is what the new schema says a missing value means, which is why a
newly added field must have a default to stay readable against old
data. A field the writer had but the reader dropped is ignored,
read and discarded, because the new schema does not want it, and
this is safe precisely because the field was not required by the
reader. The resolution fails only on an incompatible type change to
a field both schemas have, because there is no meaning to reading
an integer where the reader expects a list, and guessing one would
corrupt the value. The resolver walks the reader's fields, taking
each from the record if the writer had it and the types agree,
filling from the default if the writer lacked it, and it refuses a
reader field the writer lacks that has no default, the exact case
that makes an added field break old data, naming it so the fix,
give the field a default, is obvious. It reports which fields were
filled from defaults and which writer fields were dropped, because
a record resolving mostly from defaults is one written against a
schema so old that most of the reader's fields did not exist yet,
worth knowing when the values look empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ReaderField:
    name: str
    type_name: str
    default: object = None
    has_default: bool = False


@dataclass
class SchemaResolver:
    reader_fields: list[ReaderField] = field(default_factory=list)

    def resolve(
        self, record: dict[str, object], writer_types: dict[str, str]
    ) -> dict[str, object]:
        out: dict[str, object] = {}
        for rf in self.reader_fields:
            if rf.name in record:
                if writer_types.get(rf.name) != rf.type_name:
                    raise Invalid(
                        f"field '{rf.name}' is {writer_types.get(rf.name)} in "
                        f"the writer but {rf.type_name} in the reader; an "
                        "incompatible type change with no safe reading"
                    )
                out[rf.name] = record[rf.name]
            elif rf.has_default:
                out[rf.name] = rf.default
            else:
                raise Invalid(
                    f"reader field '{rf.name}' is absent from the writer and "
                    "has no default; give it a default or it breaks old data"
                )
        return out

    def dropped_fields(self, record: dict[str, object]) -> list[str]:
        reader_names = {rf.name for rf in self.reader_fields}
        return sorted(k for k in record if k not in reader_names)

    def report(
        self, record: dict[str, object], writer_types: dict[str, str]
    ) -> str:
        resolved = self.resolve(record, writer_types)
        filled = [rf.name for rf in self.reader_fields if rf.name not in record]
        dropped = self.dropped_fields(record)
        return (
            f"resolved {len(resolved)} field(s); {len(filled)} filled from "
            f"defaults, {len(dropped)} writer field(s) dropped; mostly "
            "defaults means a record written against a much older schema"
        )
