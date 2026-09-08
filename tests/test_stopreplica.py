from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.stopreplica import ReplicaHost


def _host():
    return ReplicaHost(
        hosted={"t-0", "t-1"},
        leading=set(),
        on_disk={"t-0", "t-1"},
    )


class TestStopKeep:
    def test_stop_and_keep_leaves_the_log_on_disk(self):
        h = _host()
        note = h.stop_replica("t-0", delete=False)
        assert "log kept on disk" in note
        assert "t-0" not in h.hosted
        assert "t-0" in h.on_disk


class TestStopDelete:
    def test_stop_and_delete_reclaims_the_disk(self):
        h = _host()
        note = h.stop_replica("t-0", delete=True)
        assert "disk reclaimed" in note
        assert "t-0" not in h.on_disk


class TestRefusals:
    def test_an_unhosted_partition_is_missing(self):
        h = _host()
        with pytest.raises(Missing) as caught:
            h.stop_replica("t-9", delete=True)
        assert "already gone" in str(caught.value)

    def test_stopping_a_live_leader_is_refused(self):
        h = ReplicaHost(hosted={"t-0"}, leading={"t-0"}, on_disk={"t-0"})
        with pytest.raises(Invalid) as caught:
            h.stop_replica("t-0", delete=False)
        assert "move leadership first" in str(caught.value)
