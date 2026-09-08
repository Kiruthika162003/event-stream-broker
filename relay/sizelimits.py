"""Size limits: a record too big fails at the earliest gate, most cheaply.

A record travels through a series of size gates, the producer's
batch limit, the request size limit, the broker's message limit,
the topic's max message override, and it must pass all of them.
The question the validator answers is where a too-large record
should fail, and the answer is the earliest gate that can catch
it, because a record rejected at the producer never crosses the
network, while the same record rejected at the broker wasted the
bandwidth to send it. So the validator checks the producer-side
limits first and only appeals to the broker limits for what the
producer could not know, and it names which gate rejected a
record, because a producer that gets a generic too-large error
cannot tell whether to split the record, raise its own batch
limit, or ask the operator to raise the topic limit, and those
are three different fixes. The subtle case is the topic override:
a topic can allow larger messages than the broker default, so a
record that exceeds the broker default but fits the topic limit
is valid, and a validator that checked the broker default without
the topic override would reject records the topic was explicitly
configured to accept, the config change having been made
precisely to allow them. The validator resolves the effective
limit as the topic override where present, falling back to the
broker default, so the limit a record is checked against is the
one that actually applies, not the one that would apply to a
different topic.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass(frozen=True)
class SizeLimits:
    producer_batch_max: int
    request_max: int
    broker_message_max: int
    topic_override: int | None = None

    def effective_message_max(self) -> int:
        if self.topic_override is not None:
            return self.topic_override
        return self.broker_message_max


def validate_record(
    limits: SizeLimits, record_size: int
) -> str:
    effective = limits.effective_message_max()
    if record_size > limits.producer_batch_max:
        raise Invalid(
            f"record of {record_size} exceeds the producer batch "
            f"limit {limits.producer_batch_max}; rejected at the "
            "cheapest gate before crossing the network, split the "
            "record or raise the batch limit"
        )
    if record_size > limits.request_max:
        raise Invalid(
            f"record of {record_size} exceeds the request limit "
            f"{limits.request_max}; still producer-side, no "
            "bandwidth wasted"
        )
    if record_size > effective:
        source = (
            "topic override"
            if limits.topic_override is not None
            else "broker default"
        )
        raise Invalid(
            f"record of {record_size} exceeds the effective "
            f"message limit {effective} ({source}); ask the "
            "operator to raise the topic limit, a different fix "
            "from splitting"
        )
    return (
        f"record of {record_size} fits every gate up to the "
        f"effective limit {effective}"
    )
