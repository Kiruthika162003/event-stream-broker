from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.offlinepartition import PartitionAvailability, Replica


class TestOnline:
    def test_an_available_in_sync_replica_keeps_it_online(self):
        p = PartitionAvailability(
            replicas=[
                Replica("b1", available=True, in_sync=True),
                Replica("b2", available=False, in_sync=True),
            ]
        )
        assert p.is_online()
        assert p.leader() == "b1"

    def test_no_available_in_sync_replica_is_offline(self):
        p = PartitionAvailability(
            replicas=[
                Replica("b1", available=False, in_sync=True),
                Replica("b2", available=True, in_sync=False),
            ]
        )
        assert not p.is_online()

    def test_unclean_election_brings_an_out_of_sync_replica_up(self):
        p = PartitionAvailability(
            replicas=[Replica("b2", available=True, in_sync=False)],
            allow_unclean=True,
        )
        assert p.is_online()
        assert p.leader() == "b2"


class TestOfflineRefusals:
    def test_an_offline_partition_refuses_to_name_a_leader(self):
        p = PartitionAvailability(
            replicas=[Replica("b1", available=False, in_sync=True)]
        )
        with pytest.raises(Invalid) as caught:
            p.leader()
        assert "routing produce to a dead leader" in str(caught.value)


class TestWhyOffline:
    def test_all_down_is_named(self):
        p = PartitionAvailability(
            replicas=[Replica("b1", available=False, in_sync=True)]
        )
        assert "all replicas down" in p.why_offline()

    def test_in_sync_lost_is_named(self):
        p = PartitionAvailability(
            replicas=[Replica("b2", available=True, in_sync=False)]
        )
        assert "unclean election disabled" in p.why_offline()


class TestUncleanRecovery:
    def test_it_states_the_cost_of_going_unclean(self):
        p = PartitionAvailability(
            replicas=[Replica("b2", available=True, in_sync=False)]
        )
        note = p.unclean_recovery()
        assert "would let b2 lead" in note
        assert "records it never replicated" in note
