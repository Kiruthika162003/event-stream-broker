"""Broker id conflict: two brokers with one id is a corruption nobody sees.

Every broker has a numeric id that the cluster uses to track
which broker leads what and holds which replicas, and the id is
supposed to be unique, but a misconfiguration, a cloned VM image,
a copy-pasted config, a recycled id after a decommission, can put
two live brokers on the same id. The failure is uniquely nasty
because it is silent: the cluster sees one id, routes to it, and
the two brokers each think they are that broker, so replica
assignments and leadership land on whichever one answered,
non-deterministically, and the log for a partition can end up
split across two machines that both believe they hold it. The
detector catches a conflict at registration: a broker registering
an id already held by a live broker with a different incarnation,
a startup-time random nonce, is a conflict, and it is refused,
because admitting the second broker is admitting the corruption.
The incarnation is the key idea: the same broker restarting
re-registers its id with a new incarnation and that is fine, a
legitimate restart, while a different broker claiming the id
brings a different incarnation against a still-live registration,
which is the conflict. The detector distinguishes the two, a
restart from a conflict, by whether the previous registration is
still live, so a broker that crashed and restarts is welcomed
while a second broker impersonating a live one is refused, and it
names the conflict with both incarnations, because an operator
seeing id 5 refused needs to know it is a duplicate, not a
transient, and go find the cloned config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class BrokerRegistry:
    live: dict[int, str] = field(default_factory=dict)

    def register(
        self,
        broker_id: int,
        incarnation: str,
        previous_alive: bool,
    ) -> str:
        held = self.live.get(broker_id)
        if held is not None and held != incarnation and previous_alive:
            raise Invalid(
                f"broker id {broker_id} conflict: incarnation "
                f"{incarnation} claims an id a live broker "
                f"({held}) holds; refused, because admitting it "
                "admits a corruption where two machines split one "
                "partition's log. Find the cloned config"
            )
        restart = held is not None and held != incarnation
        self.live[broker_id] = incarnation
        if restart:
            return (
                f"broker id {broker_id} re-registered with a new "
                "incarnation, a legitimate restart of a dead "
                "broker"
            )
        return f"broker id {broker_id} registered ({incarnation})"

    def deregister(self, broker_id: int) -> None:
        self.live.pop(broker_id, None)

    def is_conflict(
        self,
        broker_id: int,
        incarnation: str,
        previous_alive: bool,
    ) -> bool:
        held = self.live.get(broker_id)
        return (
            held is not None
            and held != incarnation
            and previous_alive
        )
