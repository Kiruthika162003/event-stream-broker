"""Global table: replicate the whole table everywhere to escape co-partitioning.

A stream-to-table join normally requires co-partitioning, the same
key on both sides landing on the same task, which forces the table
to be partitioned exactly like the stream and forbids joining on
any key but the partition key. A global table lifts that
restriction by giving up partitioning entirely: the table is
replicated in full to every processing instance, so any task can
look up any key locally, which lets a stream join the table on a
field that is not the stream's partition key, the classic case
being enriching events with a reference dataset like a lookup of
country codes. The cost is memory and startup: every instance holds
the entire table, so a global table must be small enough to fit in
each instance many times over, and each instance must load the
whole table before it can process, because a join against a table
still loading would miss keys not yet read. This is the tradeoff
the model makes explicit: a global table trades the co-partitioning
constraint for a full copy on every instance, which is right for a
small slowly-changing dataset and wrong for a large one. The table
refuses to be declared global when its estimated size against the
instance memory budget exceeds a safe fraction, because a global
table that does not fit is a memory failure on every instance at
once rather than on one. It refuses lookups before its initial load
completes, the same discipline as the state store, because a lookup
into a half-loaded table returns a wrong miss. The report states
the per-instance footprint times the instance count, the total
memory the choice costs across the cluster, because a global table
is cheap per key and expensive per instance, and the multiplication
is the number worth seeing before declaring one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class GlobalTable:
    estimated_bytes: int
    instance_memory: int
    instances: int
    safe_fraction: float = 0.25
    loaded: bool = False
    data: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        budget = self.instance_memory * self.safe_fraction
        if self.estimated_bytes > budget:
            raise Invalid(
                f"a global table of {self.estimated_bytes} bytes "
                f"exceeds the safe {self.safe_fraction:.0%} of each "
                f"instance's {self.instance_memory}; it would fail on "
                "every instance at once, not one"
            )

    def finish_load(self, rows: dict[str, str]) -> None:
        self.data = dict(rows)
        self.loaded = True

    def lookup(self, key: str) -> str:
        if not self.loaded:
            raise Invalid(
                "the global table is still loading; a lookup now "
                "returns a wrong miss for a key not yet read"
            )
        if key not in self.data:
            raise Invalid(f"no row for key '{key}' in the global table")
        return self.data[key]

    def cluster_footprint(self) -> str:
        total = self.estimated_bytes * self.instances
        return (
            f"{self.estimated_bytes} byte(s) on each of {self.instances} "
            f"instance(s) = {total} across the cluster; cheap per key, "
            "expensive per instance, and this is the multiplication to "
            "see before declaring one global"
        )
