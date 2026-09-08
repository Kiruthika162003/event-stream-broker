from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicaselector import ReplicaSelector


def _sel() -> ReplicaSelector:
    s = ReplicaSelector(leader="b1")
    s.add_replica("b1", "rack-a", 100, in_sync=True)
    s.add_replica("b2", "rack-b", 98, in_sync=True)
    s.add_replica("b3", "rack-b", 99, in_sync=True)
    return s


class TestSelect:
    def test_a_local_in_sync_follower_is_chosen(self):
        s = _sel()
        broker, how = s.select("rack-b")
        assert how == "local hit"
        assert broker in {"b2", "b3"}

    def test_the_freshest_local_follower_wins(self):
        s = _sel()
        broker, _how = s.select("rack-b")
        assert broker == "b3"  # 99 beats 98

    def test_no_local_replica_falls_back_to_the_leader(self):
        s = _sel()
        broker, how = s.select("rack-c")
        assert broker == "b1"
        assert how == "leader fallback"

    def test_an_out_of_sync_local_replica_is_not_chosen(self):
        s = ReplicaSelector(leader="b1")
        s.add_replica("b1", "rack-a", 100, in_sync=True)
        s.add_replica("b2", "rack-b", 90, in_sync=False)  # local but lagging
        broker, how = s.select("rack-b")
        assert broker == "b1"
        assert how == "leader fallback"


class TestRefusal:
    def test_no_in_sync_replica_at_all_is_refused(self):
        s = ReplicaSelector(leader="b1")
        s.add_replica("b1", "rack-a", 100, in_sync=False)
        with pytest.raises(Invalid) as caught:
            s.select("rack-a")
        assert "nothing safe to read" in str(caught.value)


class TestStaleness:
    def test_a_follower_reports_its_lag_behind_the_leader(self):
        s = _sel()
        assert s.staleness("b2") == 2  # 100 - 98

    def test_the_leader_lags_itself_by_zero(self):
        s = _sel()
        assert s.staleness("b1") == 0

    def test_an_unknown_replica_has_no_staleness(self):
        s = _sel()
        with pytest.raises(Invalid):
            s.staleness("nope")


class TestNote:
    def test_the_note_names_the_choice_and_lag(self):
        s = _sel()
        note = s.note("rack-b")
        assert "local hit" in note
        assert "behind the leader" in note
