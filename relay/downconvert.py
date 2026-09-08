"""Down-conversion: serving old clients the new format costs the zero-copy path.

The broker stores records in the newest format, and an old client
that speaks an older format needs them converted before it can
read. The conversion itself is routine; its cost is not, and the
cost is the thing operators discover during an incident. Normally
the broker serves fetches with zero-copy: the bytes go straight
from the page cache to the network socket without passing through
application memory, which is what lets one broker serve enormous
throughput. Down-conversion breaks zero-copy, because converting
the format means reading the records into memory, transforming
them, and writing them back out, so a fetch that needed
down-conversion uses CPU and memory that a normal fetch does not,
and a broker serving mostly old clients loses the efficiency that
made it fast. The insidious part is that this cost is invisible
until a fleet of old clients arrives, at which point the broker's
CPU climbs for no reason visible in the request count, because
the requests look identical and only their format differs. The
tracker counts down-converted fetches separately from zero-copy
ones and estimates the CPU premium, so the cost has a number
before it has an incident, and it names the fix that operators
reach for last: upgrade the clients, because down-conversion is a
compatibility courtesy the broker extends at its own expense, and
a broker permanently down-converting for clients nobody will ever
upgrade is subsidizing their technical debt with its throughput.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

CONVERSION_CPU_PREMIUM = 5


@dataclass
class ConversionTracker:
    zero_copy_fetches: int = 0
    down_converted_fetches: int = 0

    def serve(
        self, client_format: int, broker_format: int
    ) -> str:
        if client_format > broker_format:
            raise Invalid(
                "a client cannot ask for a newer format than the "
                "broker stores; upgrade the broker first"
            )
        if client_format == broker_format:
            self.zero_copy_fetches += 1
            return (
                "zero-copy: page cache straight to the socket, no "
                "application memory touched"
            )
        self.down_converted_fetches += 1
        return (
            f"down-converted v{broker_format} -> v{client_format}: "
            "zero-copy lost, CPU and memory spent that a normal "
            "fetch does not"
        )

    def cpu_premium(self) -> str:
        total = self.zero_copy_fetches + self.down_converted_fetches
        if total == 0:
            raise Invalid("no fetches served yet")
        premium = self.down_converted_fetches * CONVERSION_CPU_PREMIUM
        share = 100 * self.down_converted_fetches // total
        return (
            f"{self.down_converted_fetches} of {total} fetches "
            f"down-converted ({share}%), an estimated {premium} "
            "CPU unit(s) of premium; a number before an incident, "
            "and the fix operators reach for last is upgrade the "
            "clients"
        )

    def is_subsidizing(self) -> bool:
        total = self.zero_copy_fetches + self.down_converted_fetches
        if total == 0:
            return False
        return self.down_converted_fetches * 2 > total
