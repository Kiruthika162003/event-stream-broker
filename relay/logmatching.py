"""Log matching: a follower appends only where its log already agrees.

Replicating a log entry safely rests on a property: if two logs
contain an entry at the same index with the same term, then their
logs are identical in every entry up to that point. The leader
maintains this property when it sends entries by including, with
each batch, the index and term of the entry immediately before it,
and the follower appends the batch only if its own log has an entry
at that preceding index with that term. If it does, the property
guarantees everything before agrees, so appending is safe; if it
does not, the follower rejects the batch, and the leader learns
the follower's log has diverged and steps its preceding pointer
back one and retries, walking backward until it finds the last
index where the two logs agree. Once found, the follower truncates
everything after that agreement point, discarding its divergent
tail, and appends the leader's entries from there, so the two logs
converge. This backward walk is why a follower far diverged takes
several rounds to reconcile, and why the leader keeps a next-index
guess per follower that it decrements on rejection and advances on
success. The matcher checks a follower's entry at the preceding
index against the expected term, accepts and appends on a match,
rejects on a mismatch signaling the leader to back up, and refuses
to append without checking the preceding entry, the check that
upholds the property. It reports how far back the agreement point
was, because a follower that agrees only far back is one that
accepted many entries from a leader that was later deposed, a
divergence the size of the failover it lived through."
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class FollowerLog:
    # index -> term
    entries: dict[int, int] = field(default_factory=dict)

    def append(self, prev_index: int, prev_term: int, new: dict[int, int]) -> str:
        # the log-matching check: the entry before the batch must agree
        if prev_index > 0:
            have = self.entries.get(prev_index)
            if have != prev_term:
                raise Invalid(
                    f"log mismatch at index {prev_index}: have term {have}, "
                    f"leader expects {prev_term}; reject so the leader backs up"
                )
        # agreement found: truncate any divergent tail after prev_index, append
        self.entries = {i: t for i, t in self.entries.items() if i <= prev_index}
        self.entries.update(new)
        return f"appended after index {prev_index}; divergent tail truncated"

    def agreement_point(self, leader: dict[int, int]) -> int:
        point = 0
        for index in sorted(leader):
            if self.entries.get(index) == leader[index]:
                point = index
            else:
                break
        return point

    def report(self, leader: dict[int, int]) -> str:
        point = self.agreement_point(leader)
        behind = max(leader, default=0) - point
        return (
            f"logs agree through index {point}, {behind} entry(ies) to "
            "reconcile; a far-back agreement is a divergence the size of a "
            "failover the follower lived through"
        )
