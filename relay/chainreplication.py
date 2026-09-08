"""Chain replication: write at the head, read at the tail, always consistent.

Chain replication arranges the replicas in a line rather than a set:
a write enters at the head, flows down the chain node by node, and
is acknowledged only when it reaches the tail, and every read is
served by the tail. This gives strong consistency by construction:
the tail has a write only after every node before it does, so a read
from the tail never sees a write that is not fully replicated, and
never misses one that is, without the tail needing to consult
anyone. It is a different shape from quorum replication, which reads
and writes to overlapping majorities; chain replication puts all
reads on one node, the tail, and all writes through the whole chain,
trading the quorum's balanced load for simpler consistency and a
different failure profile. The failure handling is the interesting
part. A head failure loses only writes it had not yet passed on, and
the next node becomes the new head. A tail failure promotes the
node before it, which already has everything the tail had, so no
committed read is lost. A middle node failing is repaired by
linking its predecessor to its successor and letting the successor
catch up on anything the failed node had not forwarded. The chain
routes a write to the head and a read to the tail, refusing a write
sent to a non-head or a read from a non-tail, because serving a read
from a middle node could return a write the tail has not committed,
breaking the consistency the arrangement provides. It reports the
chain order and which node is head and tail, because a repair that
left the chain in the wrong order would route reads to a node that
is not the tail, silently serving uncommitted writes."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ChainReplication:
    chain: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.chain:
            raise Invalid("a chain needs at least one node")

    def head(self) -> str:
        return self.chain[0]

    def tail(self) -> str:
        return self.chain[-1]

    def write(self, node: str) -> str:
        if node != self.head():
            raise Invalid(
                f"writes enter at the head '{self.head()}', not '{node}'; a "
                "write elsewhere would not flow down the whole chain"
            )
        return f"write accepted at head '{node}', flows to tail '{self.tail()}' to commit"

    def read(self, node: str) -> str:
        if node != self.tail():
            raise Invalid(
                f"reads are served by the tail '{self.tail()}', not '{node}'; a "
                "middle node could return a write the tail has not committed"
            )
        return f"read served by tail '{node}', sees only fully-replicated writes"

    def fail(self, node: str) -> str:
        if node not in self.chain:
            raise Invalid(f"'{node}' is not in the chain")
        was_head = node == self.head()
        was_tail = node == self.tail()
        self.chain.remove(node)
        if not self.chain:
            raise Invalid("the last node failed; the chain is gone")
        if was_head:
            return f"head failed; '{self.head()}' is the new head"
        if was_tail:
            return f"tail failed; '{self.tail()}' promoted, it had everything the tail had"
        return "middle node failed; predecessor relinked to successor, chain repaired"

    def report(self) -> str:
        return (
            f"chain {' -> '.join(self.chain)}; head '{self.head()}' takes "
            f"writes, tail '{self.tail()}' serves reads, a wrong order after "
            "repair would serve uncommitted writes"
        )
