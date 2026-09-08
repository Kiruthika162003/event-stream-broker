"""Schemas: the contract between a producer's past and a consumer's future.

A topic's records share a schema, and the schema evolves, and
the whole question is whether an old reader can read new data
and a new reader can read old data. The registry enforces a
compatibility mode per topic and rejects an incompatible
evolution at registration time, before a single unreadable
record is written, because a schema break discovered at consume
time is a break discovered by every consumer at once. Backward
compatibility lets a new schema read old data, so adding an
optional field is fine and removing a required one is not.
Forward compatibility lets an old schema read new data, so
removing an optional field is fine and adding a required one is
not. Full compatibility demands both and is the strictest
contract, and the registry states which rule a proposed change
violated and how to make it compatible, because a rejection
that says only no teaches nothing, while one that says make the
new field optional ends the argument.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

BACKWARD = "backward"
FORWARD = "forward"
FULL = "full"
NONE = "none"
MODES = (BACKWARD, FORWARD, FULL, NONE)


@dataclass(frozen=True)
class Field:
    name: str
    required: bool


@dataclass(frozen=True)
class Schema:
    version: int
    fields: tuple[Field, ...]

    def field_names(self) -> set[str]:
        return {f.name for f in self.fields}

    def required_names(self) -> set[str]:
        return {f.name for f in self.fields if f.required}


def _backward_ok(old: Schema, new: Schema) -> str | None:
    dropped_required = old.required_names() - new.field_names()
    if dropped_required:
        return (
            f"backward broken: required field(s) "
            f"{sorted(dropped_required)} removed, so the new "
            "schema cannot read old records that carried them"
        )
    added_required = {
        f.name
        for f in new.fields
        if f.required and f.name not in old.field_names()
    }
    if added_required:
        return (
            f"backward broken: required field(s) "
            f"{sorted(added_required)} added with no default, "
            "so old records lack them; make the new field "
            "optional and it is compatible"
        )
    return None


def _forward_ok(old: Schema, new: Schema) -> str | None:
    return _backward_ok(new, old)


@dataclass
class SchemaRegistry:
    modes: dict[str, str] = field(default_factory=dict)
    schemas: dict[str, list[Schema]] = field(
        default_factory=dict
    )

    def set_mode(self, topic: str, mode: str) -> None:
        if mode not in MODES:
            raise Invalid(f"unknown compatibility mode {mode}")
        self.modes[topic] = mode

    def register(self, topic: str, schema: Schema) -> str:
        mode = self.modes.get(topic, BACKWARD)
        history = self.schemas.setdefault(topic, [])
        if history:
            latest = history[-1]
            problem = None
            if mode in (BACKWARD, FULL):
                problem = _backward_ok(latest, schema)
            if problem is None and mode in (FORWARD, FULL):
                problem = _forward_ok(latest, schema)
            if problem is not None:
                raise Invalid(
                    f"{topic} rejects version {schema.version}: "
                    f"{problem}"
                )
        history.append(schema)
        return (
            f"{topic} accepted version {schema.version} under "
            f"{mode} compatibility"
        )
