"""Topic config: overrides are validated against reality, not just syntax.

A topic inherits broker defaults and may override them, and the
override is where operators hurt themselves in ways a syntax
check never catches. Setting a topic's retention shorter than
its consumers' worst lag deletes data before they read it.
Setting min-in-sync-replicas higher than the replication factor
makes every acks-all produce block forever, because the required
count of replicas does not exist. Setting max-message-bytes above
the broker's fetch-max-bytes creates records producers can write
but consumers can never fetch, poison by configuration. The
validator checks each override against the constraints it can
actually violate, not merely that the value parses, and the
rejection explains the interaction, because "retention 60s"
looks fine in isolation and is a data-loss bug next to a consumer
that lags 90 seconds. Defaults that were never overridden are
reported as inherited, so an operator reading a topic's config
can tell a deliberate choice from an accident of inheritance,
which is the difference between a setting and a leftover.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

DEFAULTS = {
    "retention_ticks": 604800,
    "min_in_sync": 2,
    "max_message_bytes": 1000000,
}


@dataclass
class TopicConfig:
    replication_factor: int
    broker_fetch_max_bytes: int
    worst_consumer_lag_ticks: int
    overrides: dict[str, int] = field(default_factory=dict)

    def get(self, key: str) -> int:
        return self.overrides.get(key, DEFAULTS[key])

    def set(self, key: str, value: int) -> str:
        if key not in DEFAULTS:
            raise Invalid(f"unknown config key {key}")
        if (
            key == "retention_ticks"
            and value < self.worst_consumer_lag_ticks
        ):
            raise Invalid(
                f"retention {value} is below the worst "
                f"consumer lag {self.worst_consumer_lag_ticks}; "
                "this deletes data before it is read, a loss "
                "that looks fine in isolation"
            )
        if key == "min_in_sync" and value > self.replication_factor:
            raise Invalid(
                f"min-in-sync {value} exceeds the replication "
                f"factor {self.replication_factor}; every "
                "acks-all produce would block forever waiting "
                "for replicas that do not exist"
            )
        if (
            key == "max_message_bytes"
            and value > self.broker_fetch_max_bytes
        ):
            raise Invalid(
                f"max-message {value} exceeds the broker "
                f"fetch-max {self.broker_fetch_max_bytes}; "
                "producers could write records consumers can "
                "never fetch, poison by configuration"
            )
        self.overrides[key] = value
        return f"{key} set to {value}"

    def describe(self) -> str:
        lines = []
        for key in sorted(DEFAULTS):
            if key in self.overrides:
                lines.append(
                    f"{key} = {self.overrides[key]} (override)"
                )
            else:
                lines.append(
                    f"{key} = {DEFAULTS[key]} (inherited)"
                )
        return "\n".join(lines)
