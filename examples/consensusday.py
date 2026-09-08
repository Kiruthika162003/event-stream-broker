"""A consensus day: elect a leader, replicate the log, commit, read, grow.

Run with: python -m examples.consensusday
"""

from __future__ import annotations

from relay.commitindex import CommitIndex
from relay.logmatching import FollowerLog
from relay.membershipchange import Membership
from relay.quorumvote import Election, LogEnd
from relay.readindex import ReadIndex


def morning_elect_a_leader():
    election = Election(term=4, voters=3)
    cand = LogEnd(last_term=3, length=100)
    election.request_vote("v1", cand, LogEnd(3, 100))
    election.request_vote("v2", cand, LogEnd(3, 90))
    print(f"morning: {election.tally()}")


def midmorning_replicate_the_log():
    follower = FollowerLog(entries={1: 3, 2: 3})
    print(f"         {follower.append(prev_index=2, prev_term=3, new={3: 4, 4: 4})}")


def noon_commit_current_term():
    ci = CommitIndex(current_term=4, entry_terms={1: 3, 2: 3, 3: 4}, voters=3)
    print(f"noon:    {ci.try_advance(3, replica_count=2)}")


def afternoon_a_linearizable_read():
    r = ReadIndex(commit_index=100, voters=3)
    r.begin_read()
    r.confirm()
    r.apply_to(100)
    print(f"afternoon: {r.serve()}")


def evening_grow_the_cluster():
    m = Membership(voters={"v1", "v2", "v3"})
    print(f"evening: {m.change_to({'v1', 'v2', 'v3', 'v4'})}")


def main() -> int:
    morning_elect_a_leader()
    midmorning_replicate_the_log()
    noon_commit_current_term()
    afternoon_a_linearizable_read()
    evening_grow_the_cluster()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
