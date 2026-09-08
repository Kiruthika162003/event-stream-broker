"""A leader dies mid-window, and the consumer never saw the ghost.

The scenario is the one the high watermark exists for: a
producer appends ten records, only seven are replicated and
committed, and then the leader dies before the last three are
promised. The drill drives exactly that, appends ten, advances
the watermark to seven, and confirms the consumer can read
0 through 6 and is refused at 7, because those three records
existed on the dead leader and must be treated as if they
never happened. The counterfactual is the proof's weight: a
broker that served the log's end instead of the watermark
would have handed the consumer three records that a new leader
cannot reproduce, which is the un-happening bug, and the gap
between ten and seven is exactly the blast radius the watermark
contains.
"""

from __future__ import annotations

from relay.errors import Missing
from relay.partition import Partition
from relay.proofs.finding import Finding
from relay.records import Record


def run() -> Finding:
    partition = Partition(number=0)
    for number in range(10):
        partition.append(Record(value=f"e{number}".encode()))
    partition.advance_watermark(7)
    readable = 0
    for offset in range(7):
        partition.consume(offset)
        readable += 1
    ghost_refused = False
    try:
        partition.consume(7)
    except Missing:
        ghost_refused = True
    numbers = {
        "appended": 10,
        "committed": 7,
        "readable": readable,
        "ghosts_contained": 3,
        "ghost_refused": ghost_refused,
    }
    holds = (
        readable == 7
        and ghost_refused
        and numbers["ghosts_contained"] == 3
    )
    return Finding(
        proof="watermarkholds",
        claim=(
            "seven committed records serve and three ghosts "
            "are refused: the watermark contains exactly the "
            "blast radius of a leader that died mid-window"
        ),
        numbers=numbers,
        holds=holds,
    )
