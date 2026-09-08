"""LRU cache: a bounded cache that evicts what was used longest ago.

A broker caches things it wants fast access to but cannot hold all
of, metadata for many topics, open fetch sessions, recently read
keys, and it needs the cache bounded so it does not grow without
limit. An LRU cache bounds it by evicting, when full, the entry
used least recently, on the bet that what was used recently will be
used again and what has not been touched in a while will not. Every
access, read or write, marks an entry as most recently used, so the
least recently used naturally falls to the back and is the one
evicted next, which keeps the working set, the entries actually
being used, in the cache while cold entries age out. This suits a
broker's access pattern, where a few topics or sessions are hot and
the long tail is rarely touched, so the LRU keeps the hot ones
resident and spends its capacity where it helps. The catch the LRU
does not handle is a scan, a pass over many entries each used once,
which evicts the hot working set in favor of entries that will not
be used again, the reason a large sequential scan can cold-start a
cache, and an operator seeing a cache hit rate collapse during a
batch job is usually seeing exactly that. The cache tracks order,
moves an entry to most-recent on access, evicts the least-recent on
a put that overflows, and reports the hit rate so the cache's value
is measured rather than assumed. It refuses a zero capacity, which
caches nothing, and a get of an absent key returns a miss rather
than an error, because a miss is a normal outcome the caller
handles by fetching the real value."
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class LruCache:
    capacity: int
    _store: OrderedDict = field(default_factory=OrderedDict)
    hits: int = 0
    misses: int = 0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise Invalid("an LRU cache needs positive capacity")

    def get(self, key: str) -> int | None:
        if key not in self._store:
            self.misses += 1
            return None
        self.hits += 1
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key: str, value: int) -> str:
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = value
            return f"updated '{key}'"
        self._store[key] = value
        if len(self._store) > self.capacity:
            evicted, _ = self._store.popitem(last=False)
            return f"put '{key}', evicted least-recent '{evicted}'"
        return f"put '{key}'"

    def keys_mru_first(self) -> list[str]:
        return list(reversed(self._store))

    def hit_rate(self) -> str:
        total = self.hits + self.misses
        if total == 0:
            return "no accesses yet"
        rate = self.hits / total * 100
        return (
            f"{rate:.0f}% hit rate ({self.hits}/{total}); a collapse during a "
            "batch job is a scan evicting the hot working set for entries used "
            "once"
        )
