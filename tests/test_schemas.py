from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.schemas import (
    BACKWARD,
    FORWARD,
    FULL,
    Field,
    Schema,
    SchemaRegistry,
)

V1 = Schema(
    version=1,
    fields=(
        Field("id", required=True),
        Field("name", required=True),
    ),
)


def registry(mode: str) -> SchemaRegistry:
    reg = SchemaRegistry()
    reg.set_mode("users", mode)
    reg.register("users", V1)
    return reg


class TestBackward:
    def test_adding_an_optional_field_is_compatible(self):
        reg = registry(BACKWARD)
        v2 = Schema(
            version=2,
            fields=(*V1.fields, Field("email", required=False)),
        )
        assert "accepted version 2" in reg.register("users", v2)

    def test_removing_a_required_field_is_rejected(self):
        reg = registry(BACKWARD)
        v2 = Schema(version=2, fields=(Field("id", required=True),))
        with pytest.raises(Invalid) as caught:
            reg.register("users", v2)
        assert "cannot read old records" in str(caught.value)

    def test_adding_a_required_field_suggests_optional(self):
        reg = registry(BACKWARD)
        v2 = Schema(
            version=2,
            fields=(*V1.fields, Field("age", required=True)),
        )
        with pytest.raises(Invalid) as caught:
            reg.register("users", v2)
        assert "make the new field optional" in str(caught.value)


class TestForward:
    def test_removing_an_optional_field_is_forward_compatible(self):
        reg = SchemaRegistry()
        reg.set_mode("users", FORWARD)
        base = Schema(
            version=1,
            fields=(
                Field("id", required=True),
                Field("nick", required=False),
            ),
        )
        reg.register("users", base)
        v2 = Schema(version=2, fields=(Field("id", required=True),))
        assert "accepted version 2" in reg.register("users", v2)


class TestFull:
    def test_full_demands_both_directions(self):
        reg = registry(FULL)
        v2_add_required = Schema(
            version=2,
            fields=(*V1.fields, Field("age", required=True)),
        )
        with pytest.raises(Invalid):
            reg.register("users", v2_add_required)

    def test_an_unknown_mode_is_refused(self):
        with pytest.raises(Invalid):
            SchemaRegistry().set_mode("users", "sideways")
