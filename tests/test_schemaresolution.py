from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.schemaresolution import ReaderField, SchemaResolver


def _resolver():
    return SchemaResolver(
        reader_fields=[
            ReaderField("id", "int"),
            ReaderField("name", "string"),
            ReaderField("region", "string", default="unknown", has_default=True),
        ]
    )


class TestResolve:
    def test_matching_fields_pass_through(self):
        r = _resolver()
        out = r.resolve(
            {"id": 1, "name": "a", "region": "us"},
            writer_types={"id": "int", "name": "string", "region": "string"},
        )
        assert out == {"id": 1, "name": "a", "region": "us"}

    def test_a_new_field_is_filled_from_the_default(self):
        r = _resolver()
        out = r.resolve(
            {"id": 1, "name": "a"},
            writer_types={"id": "int", "name": "string"},
        )
        assert out["region"] == "unknown"

    def test_a_dropped_writer_field_is_ignored(self):
        r = _resolver()
        out = r.resolve(
            {"id": 1, "name": "a", "legacy": "x"},
            writer_types={"id": "int", "name": "string", "legacy": "string"},
        )
        assert "legacy" not in out

    def test_an_incompatible_type_change_fails(self):
        r = _resolver()
        with pytest.raises(Invalid) as caught:
            r.resolve(
                {"id": [1, 2], "name": "a"},
                writer_types={"id": "list", "name": "string"},
            )
        assert "incompatible type change" in str(caught.value)

    def test_a_new_field_without_a_default_breaks_old_data(self):
        r = SchemaResolver(reader_fields=[ReaderField("added", "int")])
        with pytest.raises(Invalid) as caught:
            r.resolve({}, writer_types={})
        assert "give it a default" in str(caught.value)


class TestReport:
    def test_report_counts_filled_and_dropped(self):
        r = _resolver()
        note = r.report(
            {"id": 1, "name": "a", "legacy": "x"},
            writer_types={"id": "int", "name": "string", "legacy": "string"},
        )
        assert "1 filled from defaults" in note
        assert "1 writer field(s) dropped" in note
