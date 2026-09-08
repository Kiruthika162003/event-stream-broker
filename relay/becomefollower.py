"""Become follower: a demoted leader must truncate before it fetches again.

The reverse of promotion is a broker that was leading a partition
being told to follow a new leader, and its transition is the mirror
image with its own ordering hazard. The demoted broker may have
records at the end of its log that it accepted as leader but that
were never committed, records past the high watermark that the new
leader does not have, and if it started fetching from the new
leader without dealing with them it would have a log that diverges
from the leader's at the tail, two different records at the same
offset. So the order is: stop accepting produce first, because a
demoted leader still taking writes is appending records no one will
replicate, then truncate the log back to the point where it agrees
with the new leader, discarding the uncommitted tail, then start
fetching from the new leader to refill from the truncation point
forward. The truncation point is found from the leader epoch: the
demoted broker asks the new leader for the end of the last epoch
they share and truncates to there, the same divergence logic
recovery uses, because a divergence can only begin at an epoch
boundary. The transition refuses to fetch before truncating,
because fetching onto an un-truncated diverging tail would append
the leader's records after its own conflicting ones, leaving a log
that is neither its old one nor the leader's. It refuses to keep
serving produce once demotion begins, and refuses a truncation
point above its own log end, which would be a leader claiming this
broker has records it does not. The report states how many records
were discarded in truncation, because a large truncation is a
broker that had accepted many uncommitted records before losing
leadership, the blast radius of the failover it just went through.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class FollowerTransition:
    log_end: int
    high_watermark: int
    serving: bool = True
    truncated_to: int = -1
    fetching: bool = False

    def stop_serving(self) -> str:
        self.serving = False
        return "stopped accepting produce; a demoted leader takes no writes"

    def truncate(self, divergence_offset: int) -> str:
        if self.serving:
            raise Invalid(
                "still serving produce; stop accepting writes before "
                "truncating or the tail keeps growing"
            )
        if divergence_offset > self.log_end:
            raise Invalid(
                f"truncation point {divergence_offset} is past this "
                f"broker's log end {self.log_end}; the leader claims "
                "records this broker does not have"
            )
        discarded = self.log_end - divergence_offset
        self.log_end = divergence_offset
        self.truncated_to = divergence_offset
        return (
            f"truncated to {divergence_offset}, discarded {discarded} "
            "uncommitted record(s) from the tail"
        )

    def start_fetching(self) -> str:
        if self.truncated_to < 0:
            raise Invalid(
                "cannot fetch before truncating; fetching onto a "
                "diverging tail leaves a log neither this broker's nor "
                "the leader's"
            )
        self.fetching = True
        return f"fetching from the new leader, resuming at {self.truncated_to}"
