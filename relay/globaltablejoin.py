"""Global table join: enrich a stream on any key, because the table is everywhere.

Joining a stream to a table on the stream's partition key needs
co-partitioning, but often the join key is not the partition key: a
stream of orders partitioned by order id, enriched with customer
details keyed by customer id. A stream-to-global-table join handles
that without repartitioning the stream. Because the global table is
replicated in full to every task, any task can look up any key
locally, so the join extracts a foreign key from each stream record
and looks it up in the table wherever the record happens to be, no
shuffle required. This is the payoff of the global table's cost:
the full replication that makes it expensive in memory is exactly
what lets the join skip the repartition a co-partitioned join would
need. The join is stream-driven, not table-driven: it fires on each
stream record, looking up the current table value, so unlike a
table-to-table join it does not re-emit when the table changes,
which fits enrichment where the stream is the event and the table
is reference data. A stream record whose foreign key is absent from
the table is handled by the join type: an inner join drops it, a
left join passes it through with a null enrichment, and the choice
matters because dropping silently loses events whose reference data
has not loaded yet. The join extracts the foreign key, looks it up,
and applies the inner or left policy, refusing an unknown join type,
and it reports the miss rate, because a stream mostly missing the
table is either a foreign key extracted wrong or a table not fully
loaded, both of which drop or null-enrich events that should have
matched.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from relay.errors import Invalid

INNER = "inner"
LEFT = "left"


@dataclass
class GlobalTableJoin:
    table: dict[str, str]
    foreign_key: Callable[[dict], str]
    join_type: str = INNER
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        if self.join_type not in (INNER, LEFT):
            raise Invalid(f"unknown join type '{self.join_type}'")

    def join(self, record: dict) -> dict | None:
        fk = self.foreign_key(record)
        if fk in self.table:
            self.hits += 1
            return {**record, "enriched": self.table[fk]}
        self.misses += 1
        if self.join_type == LEFT:
            return {**record, "enriched": None}
        return None  # inner join drops an unmatched record

    def join_batch(self, records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            joined = self.join(r)
            if joined is not None:
                out.append(joined)
        return out

    def miss_rate(self) -> str:
        total = self.hits + self.misses
        if total == 0:
            return "no records joined yet"
        pct = self.misses / total * 100
        return (
            f"{self.misses}/{total} missed the table ({pct:.0f}%); mostly "
            "missing is a foreign key extracted wrong or a table not fully "
            "loaded, dropping or null-enriching events that should have matched"
        )
