"""Consumer close: leave the group on the way out, or the others wait for you.

Closing a consumer cleanly is more than stopping the poll loop,
because the consumer is a member of a group and its departure
affects the others. A clean close does two things in order. It
commits its final offsets if it was managing them, so the position
it reached is saved and whoever picks up its partitions resumes
there rather than reprocessing back to the last periodic commit.
Then it sends an explicit leave-group to the coordinator, which is
the part that helps the rest of the group: the coordinator, told a
member is gone, starts a rebalance immediately and reassigns that
member's partitions to the survivors. A consumer that dies without
leaving, crashed or killed, does not send that message, so the
coordinator does not know it is gone until the member misses
heartbeats for the whole session timeout, and until then the dead
member's partitions are owned by no one and consumed by no one, a
gap of unavailability as long as the session timeout that a clean
close avoids entirely. The closer commits then leaves in that order,
because leaving before committing would let the rebalance reassign
the partitions before the final offsets were saved, and the new
owner would reprocess the gap. It refuses to poll after close
begins, the same discipline as the producer, and refuses to leave
twice. The report states whether the close was clean or the member
was left to time out, because a group repeatedly waiting session
timeouts for departed members is one whose consumers are being
killed rather than closed, worth fixing at the source.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class ConsumerClose:
    position: int
    committed: int = 0
    closing: bool = False
    left_group: bool = False

    def poll(self) -> str:
        if self.closing:
            raise Invalid(
                "poll refused: the consumer is closing; no more records "
                "after close begins"
            )
        return "polled"

    def close(self) -> str:
        if self.left_group:
            raise Invalid("already closed; a second leave is a bug")
        self.closing = True
        # commit before leaving, or the rebalance reassigns before the
        # final offsets are saved and the new owner reprocesses the gap
        self.committed = self.position
        self.left_group = True
        return (
            f"clean close: committed final offset {self.committed}, then "
            "sent leave-group so the coordinator rebalances now, not after "
            "the session timeout"
        )

    @staticmethod
    def crashed_cost(session_timeout: int) -> str:
        return (
            f"a consumer that crashed without leaving strands its "
            f"partitions for the whole {session_timeout} session timeout "
            "before the coordinator reassigns them, consumed by no one"
        )
