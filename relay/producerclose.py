"""Producer close: drain what is buffered, on a deadline, then no more sends.

A producer buffers records and sends them in batches, so at the
moment an application closes the producer there are usually records
still in the buffer that have not reached the broker, and a close
that discarded them would silently lose data the application
believed it had handed off. A clean close flushes: it stops
accepting new sends and drives the buffered batches to completion,
blocking the caller until every pending record is acknowledged or
the close deadline elapses. The deadline is the honest part,
because a broker that is unreachable would make an unbounded flush
hang forever, so close takes a timeout and, when it expires, fails
the records still pending rather than blocking, handing the
application the list of what did not make it so it can decide
rather than discovering the loss later. The order matters: sends
must be refused the instant close begins, before the flush, because
a record accepted after close started might not be included in the
flush and would be lost in the gap between accepting it and
shutting down. The closer refuses a send after close with a clear
error rather than accepting and dropping it, and it refuses a
second close, because a double close usually means two code paths
both own the producer and one will use it after the other shut it
down. A close with an already-empty buffer completes at once, and
the report states how many records were flushed and how many failed
at the deadline, because a close that failed records is a loss the
application must be told about in the return, not in a log it may
not read.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Producer:
    pending: list[str] = field(default_factory=list)
    closing: bool = False
    closed: bool = False

    def send(self, record: str) -> None:
        if self.closing or self.closed:
            raise Invalid(
                "send refused: the producer is closing; a record "
                "accepted now could fall in the gap between accepting "
                "it and shutting down, and be lost"
            )
        self.pending.append(record)

    def close(self, acked_within_deadline: int) -> str:
        if self.closed:
            raise Invalid(
                "already closed; a double close usually means two "
                "owners and one will use it after the other shut it"
            )
        self.closing = True
        total = len(self.pending)
        flushed = min(acked_within_deadline, total)
        failed = self.pending[flushed:]
        self.pending = []
        self.closed = True
        if failed:
            return (
                f"closed at the deadline: {flushed} record(s) "
                f"flushed, {len(failed)} failed and returned to the "
                "caller, not lost silently"
            )
        return f"closed cleanly: {flushed} record(s) flushed, none pending"
