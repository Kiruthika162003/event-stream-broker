"""OR-set: a replicated set that can remove, and a concurrent add still wins.

A grow-only set converges trivially by union but cannot remove,
because a remove is not idempotent under union, the removed element
comes back on the next merge. An observed-remove set removes
correctly by tagging. Every add of an element attaches a unique
tag, so adding the same element twice creates two distinct tags,
and a remove does not delete the element by name, it records the
specific add-tags it observed at the time. An element is in the set
if it has at least one add-tag that no remove has observed. Merge
unions the adds and unions the removes, both grow-only and so
convergent, and membership is recomputed from them. This makes the
concurrent add-remove case resolve the way people expect: if one
replica removes an element while another concurrently adds it
again, the second add created a new tag the remove never observed,
so the element stays in the set, add wins over a concurrent remove,
which is usually the safe choice because a remove should not erase
an add it never saw. The cost is the tags: the set carries a tag
per add, and removes accumulate the tags they observed, so a set
churned heavily grows metadata that needs periodic compaction, the
tradeoff for correct removal. The set adds with a fresh tag,
removes by observing an element's current tags, merges by unioning
adds and removes, and computes membership as elements with an
unremoved tag. It refuses a remove of an element not present, which
observes nothing, and reports the tag overhead, because a set whose
tag count dwarfs its element count is one needing compaction, the
metadata cost of removal made visible."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class ORSet:
    node_id: str = "n"
    adds: dict[str, set[tuple[str, int]]] = field(default_factory=dict)
    removes: set[tuple[str, int]] = field(default_factory=set)
    _next_tag: int = 0

    def add(self, element: str) -> tuple[str, int]:
        # a tag must be globally unique, so it carries this node's id, not a
        # bare counter that collides with another replica's counter
        tag = (self.node_id, self._next_tag)
        self._next_tag += 1
        self.adds.setdefault(element, set()).add(tag)
        return tag

    def remove(self, element: str) -> None:
        if not self.contains(element):
            raise Invalid(
                f"'{element}' is not present; a remove observes no tags and "
                "does nothing"
            )
        self.removes |= self.adds.get(element, set())

    def contains(self, element: str) -> bool:
        live = self.adds.get(element, set()) - self.removes
        return bool(live)

    def merge(self, other: ORSet) -> None:
        for element, tags in other.adds.items():
            self.adds.setdefault(element, set()).update(tags)
        self.removes |= other.removes
        self._next_tag = max(self._next_tag, other._next_tag)

    def elements(self) -> set[str]:
        return {e for e in self.adds if self.contains(e)}

    def tag_overhead(self) -> str:
        tags = sum(len(t) for t in self.adds.values())
        live = len(self.elements())
        return (
            f"{tags} add-tag(s) for {live} live element(s); a tag count "
            "dwarfing the elements needs compaction, the metadata cost of "
            "correct removal"
        )
