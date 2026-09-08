"""Connection reaping: a socket that stopped talking still holds a slot.

A broker has finite connection slots, and a client that opened a
connection and vanished, crashed, network-partitioned, forgot to
close, holds its slot indefinitely while sending nothing. Enough
of these and the broker refuses new connections while most of its
slots serve ghosts. The reaper closes connections idle past a
timeout, freeing the slot, but the timeout must distinguish idle
from slow: a connection mid-request, waiting on a long-poll fetch
it legitimately asked to hold, is not idle even though it sends
nothing, so the reaper measures time since the last activity of
any kind, request or response, not merely time since the last
request. The distinction matters because reaping a connection
that is correctly blocked on a long-poll it requested drops a
live consumer, which reconnects and re-establishes its fetch
session, so aggressive reaping trades a full slot table for a
reconnect storm. The reaper also protects connections with an
in-flight transaction, because closing a transactional
producer's connection mid-transaction forces a coordinator
timeout and abort that a moment's patience would have avoided,
and the report separates reaped-idle from protected-busy so a
tightening timeout shows its effect before it causes an
incident.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class Connection:
    conn_id: str
    last_activity: int
    long_polling: bool = False
    in_transaction: bool = False
    closed: bool = False


@dataclass
class ConnectionReaper:
    idle_timeout: int
    connections: dict[str, Connection] = field(
        default_factory=dict
    )
    reaped: int = 0
    protected: int = 0

    def __post_init__(self) -> None:
        if self.idle_timeout < 1:
            raise Invalid("the idle timeout must be positive")

    def register(self, conn: Connection) -> None:
        self.connections[conn.conn_id] = conn

    def touch(self, conn_id: str, now: int) -> None:
        conn = self.connections.get(conn_id)
        if conn is None or conn.closed:
            raise Invalid(f"{conn_id} is not an open connection")
        conn.last_activity = now

    def reap(self, now: int) -> list[str]:
        reaped = []
        for conn in self.connections.values():
            if conn.closed:
                continue
            if now - conn.last_activity <= self.idle_timeout:
                continue
            if conn.long_polling or conn.in_transaction:
                self.protected += 1
                continue
            conn.closed = True
            self.reaped += 1
            reaped.append(conn.conn_id)
        return sorted(reaped)

    def open_slots_freed(self) -> int:
        return self.reaped

    def report(self) -> str:
        return (
            f"{self.reaped} idle connection(s) reaped, "
            f"{self.protected} busy connection(s) protected; a "
            "tightening timeout shows its effect here before it "
            "causes a reconnect storm"
        )
