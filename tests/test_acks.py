from __future__ import annotations

import pytest

from relay.acks import ALL, LEADER, NONE, resolve_ack
from relay.errors import Invalid


class TestTheModes:
    def test_none_promises_nothing_and_says_so(self):
        ack = resolve_ack(NONE, in_sync_count=3, min_in_sync=2)
        assert not ack.durable
        assert "a leader crash the producer never hears about" in (
            ack.accepts
        )

    def test_leader_survives_a_follower_not_the_leader(self):
        ack = resolve_ack(LEADER, in_sync_count=3, min_in_sync=2)
        assert ack.durable
        assert ack.survives == "a follower's death"
        assert "leader crash before replication" in ack.accepts

    def test_all_survives_any_single_covered_failure(self):
        ack = resolve_ack(ALL, in_sync_count=3, min_in_sync=2)
        assert "any single failure" in ack.survives
        assert "3-replica set covers" in ack.survives

    def test_the_line_reads_as_a_sentence(self):
        line = resolve_ack(
            LEADER, in_sync_count=3, min_in_sync=2
        ).line()
        assert line.startswith("acks=leader: survives")


class TestRefusals:
    def test_all_below_the_floor_is_an_honest_failure(self):
        with pytest.raises(Invalid) as caught:
            resolve_ack(ALL, in_sync_count=1, min_in_sync=2)
        assert "an honest failure beats a silent hang" in str(
            caught.value
        )

    def test_an_unknown_mode_is_refused(self):
        with pytest.raises(Invalid):
            resolve_ack("some", 3, 2)
