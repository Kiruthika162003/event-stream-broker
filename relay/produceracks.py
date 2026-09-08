"""Producer acks: what each level waits for, and the loss it does or does not risk.

The acks setting is the producer's side of the durability bargain, and
each level trades latency against how much loss it can survive. Acks=0
is fire and forget: the producer does not wait for any acknowledgment,
so it has the lowest latency and the highest throughput, and it can
lose a record to any failure, even a full send buffer, without ever
knowing. Acks=1 waits for the leader to write the record to its own
log, so a record is safe against the producer or network dropping the
request, but not against the leader failing before a follower has
copied the record, in which case the acknowledged record is lost in
the leadership change. Acks=all waits for every in-sync replica to
have the record, so it survives any failure short of losing all in-
sync replicas at once, at the cost of the round trip to the slowest
in-sync follower. The subtlety the level alone does not capture is that
acks=all is only as strong as the in-sync set is deep, which is why it
is paired with a minimum in-sync replicas floor; acks=all with a floor
of one is acks=1 wearing a stronger name. The classifier maps a level
to the replicas it waits for and to the failure that would still lose
an acknowledged record, decides whether a given failure scenario loses
a record at that level, and refuses an unknown acks level, because a
value that is not 0, 1, or all is a misconfiguration that would
silently pick a default the operator did not intend. It reports the
durability and latency of a level in one line, because choosing acks
is choosing a point on that curve and the choice should be made seeing
both ends of it."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

_LEVELS = {"0", "1", "all"}


@dataclass
class ProducerAcks:
    level: str

    def __post_init__(self) -> None:
        if self.level not in _LEVELS:
            raise Invalid(
                f"acks '{self.level}' is not one of 0, 1, all; an unknown value "
                "would silently pick a default the operator did not intend"
            )

    def waits_for(self) -> str:
        return {
            "0": "nothing; fire and forget",
            "1": "the leader's own write",
            "all": "every in-sync replica",
        }[self.level]

    def loses_on(self) -> str:
        return {
            "0": "any failure, even a full send buffer, silently",
            "1": "the leader failing before a follower copied the record",
            "all": "losing all in-sync replicas at once",
        }[self.level]

    def loses_record(self, *, leader_fails_before_replication: bool) -> bool:
        # decide whether a leader-fails-before-replication scenario loses a record
        if self.level == "0":
            return True
        if self.level == "1":
            return leader_fails_before_replication
        return False  # acks=all: the record was on a follower before the ack

    def note(self) -> str:
        latency = {"0": "lowest", "1": "one write", "all": "slowest follower"}[self.level]
        return (
            f"acks={self.level} waits for {self.waits_for()}, loses on "
            f"{self.loses_on()}; latency {latency}. acks=all is only as strong "
            "as the in-sync set is deep, pair it with a min-in-sync floor"
        )
