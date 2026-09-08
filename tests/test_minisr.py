from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.minisr import MinInSyncReplicas


class TestAdmit:
    def test_acks_all_is_admitted_at_the_floor(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        assert "admitted" in m.admit(in_sync_count=2, acks="all")

    def test_acks_all_is_refused_below_the_floor(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        with pytest.raises(Invalid) as caught:
            m.admit(in_sync_count=1, acks="all")
        assert "not-enough-replicas" in str(caught.value)

    def test_a_weaker_ack_is_admitted_below_the_floor(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        # acks=1 already accepted weaker durability, the floor does not apply
        assert "does not require the floor" in m.admit(in_sync_count=1, acks="1")

    def test_acks_zero_is_admitted_with_no_replicas_in_sync(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        assert "admitted" in m.admit(in_sync_count=1, acks="0")


class TestConfig:
    def test_a_floor_above_the_replication_factor_is_refused(self):
        with pytest.raises(Invalid) as caught:
            MinInSyncReplicas(floor=4, replication_factor=3)
        assert "permanently unwritable" in str(caught.value)

    def test_a_zero_floor_is_refused(self):
        with pytest.raises(Invalid):
            MinInSyncReplicas(floor=0, replication_factor=3)

    def test_a_floor_equal_to_the_factor_is_allowed(self):
        m = MinInSyncReplicas(floor=3, replication_factor=3)
        assert "admitted" in m.admit(in_sync_count=3, acks="all")


class TestMargin:
    def test_the_margin_is_above_the_floor(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        assert m.margin(3) == 1

    def test_at_the_floor_the_note_flags_the_edge(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        assert "one replica from rejecting" in m.note(2)

    def test_above_the_floor_the_note_has_no_edge_warning(self):
        m = MinInSyncReplicas(floor=2, replication_factor=3)
        assert "one replica from rejecting" not in m.note(3)
