"""Config inherit: a value comes from the most specific level that sets it.

A broker setting like the retention time exists at three levels: a
built-in default compiled into the broker, a broker-wide override an
operator sets for the whole broker, and a per-topic override set on
one topic. The effective value for a topic is the most specific
level that has one: a topic override wins if present, otherwise the
broker-wide value, otherwise the built-in default, so a topic
inherits the broker's value until it sets its own and falls back to
the built-in only when neither above it does. This precedence is
easy to reason about and easy to misread, because a value that
looks wrong on a topic may be inherited from the broker rather than
set on the topic, and changing it on the topic and changing it on
the broker do different things: the topic change affects one topic,
the broker change affects every topic that has not overridden it.
The resolver returns not just the value but its source, because an
operator debugging a topic's behavior needs to know whether the
value they see was set on the topic, inherited from the broker, or
the compiled default, since that decides where to change it. The
resolver refuses to resolve a key that has no built-in default and
no override at any level, because a key with no value anywhere is a
typo in the key name, not a config that happens to be unset, and
returning a silent empty for it would hide the misspelling. It
reports which topic overrides diverge from the broker value,
because a fleet of topics each overriding the same key to the same
value is really a broker default waiting to be set once instead of
on every topic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Missing

TOPIC = "topic override"
BROKER = "broker override"
DEFAULT = "built-in default"


@dataclass
class ConfigResolver:
    defaults: dict[str, str] = field(default_factory=dict)
    broker: dict[str, str] = field(default_factory=dict)
    topic: dict[str, str] = field(default_factory=dict)

    def resolve(self, key: str) -> tuple[str, str]:
        if key in self.topic:
            return self.topic[key], TOPIC
        if key in self.broker:
            return self.broker[key], BROKER
        if key in self.defaults:
            return self.defaults[key], DEFAULT
        raise Missing(
            f"config key '{key}' has no value at any level; that is a "
            "typo in the key name, not an unset config, and a silent "
            "empty would hide the misspelling"
        )

    def describe(self, key: str) -> str:
        value, source = self.resolve(key)
        return f"{key} = {value} (from {source})"

    def redundant_overrides(self) -> list[str]:
        return [
            key
            for key, value in self.topic.items()
            if key in self.broker and self.broker[key] == value
        ]
