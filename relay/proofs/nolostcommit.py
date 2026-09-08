"""A leader dies with unreplicated tail, and the truncation loses only that tail.

This is the proof that the epoch handshake never discards a
committed record. The scenario: an old leader's log ends at
offset 1040, but only 1000 of those were replicated and committed
before it died, so the last 40 are unreplicated tail. A follower
that was one of the committed replicas holds up to 1000; it
becomes leader. The old leader restarts as a follower and its log
is 40 records longer, all from the epoch that just ended. The
drill runs the epoch handshake: the returning follower learns the
new leader's epoch ended at 1000, computes its truncation, and
discards exactly its 40 divergent records. The proof asserts the
truncation count equals the unreplicated tail exactly, 40, and
that the committed prefix, everything through 1000, is untouched.
The guess worth stating is the fear that motivates the whole
mechanism: that a truncation might eat a committed record and
lose acknowledged data. The measurement refutes it precisely,
truncation removes the uncommitted tail and not one record more,
because the divergence point is by construction the last
committed offset, so committed and truncated are disjoint by the
arithmetic, not by luck. The number that carries the proof is the
gap between the follower's end and the truncation point, which
equals the unreplicated tail and nothing else.
"""

from __future__ import annotations

from relay.epochfetch import DivergenceGuard, truncation_point
from relay.errors import Invalid
from relay.proofs.finding import Finding


def run() -> Finding:
    committed_offset = 1000
    old_leader_end = 1040
    unreplicated_tail = old_leader_end - committed_offset
    point, _ = truncation_point(
        follower_epoch=7,
        follower_end=old_leader_end,
        leader_epoch_end=committed_offset,
    )
    truncated = old_leader_end - point
    guard = DivergenceGuard()
    append_refused = False
    try:
        guard.require_truncation(old_leader_end, committed_offset)
    except Invalid:
        append_refused = True
    resolved = guard.resolve(truncated_to=point)
    numbers = {
        "committed_offset": committed_offset,
        "old_leader_end": old_leader_end,
        "unreplicated_tail": unreplicated_tail,
        "truncated": truncated,
        "truncation_point": point,
        "committed_prefix_untouched": point == committed_offset,
        "append_refused_until_truncated": append_refused,
    }
    holds = (
        truncated == unreplicated_tail
        and point == committed_offset
        and append_refused
        and "may append again" in resolved
    )
    return Finding(
        proof="nolostcommit",
        claim=(
            "the epoch handshake truncates exactly the "
            "unreplicated tail (40 records) and leaves the "
            "committed prefix untouched; committed and truncated "
            "are disjoint by arithmetic, not by luck"
        ),
        numbers=numbers,
        holds=holds,
    )
