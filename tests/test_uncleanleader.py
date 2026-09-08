from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.uncleanleader import UncleanLeaderElection


class TestCleanElection:
    def test_the_highest_in_sync_replica_is_elected(self):
        e = UncleanLeaderElection(committed_offset=100)
        e.set_replica("a", 100, in_sync=True)
        e.set_replica("b", 95, in_sync=True)
        result = e.elect()
        assert "clean election of 'a'" in result
        assert "no committed record is lost" in result

    def test_an_out_of_sync_replica_is_never_chosen_when_isr_is_alive(self):
        e = UncleanLeaderElection(committed_offset=100)
        e.set_replica("a", 100, in_sync=True)
        e.set_replica("b", 200, in_sync=False)  # ahead but out of sync
        assert "'a'" in e.elect()


class TestEmptyIsr:
    def test_an_empty_isr_refuses_election_by_default(self):
        e = UncleanLeaderElection(committed_offset=100)
        e.set_replica("a", 80, in_sync=False)
        with pytest.raises(Invalid) as caught:
            e.elect()
        assert "favoring durability" in str(caught.value)

    def test_unclean_election_picks_the_highest_and_reports_loss(self):
        e = UncleanLeaderElection(committed_offset=100, allow_unclean=True)
        e.set_replica("a", 80, in_sync=False)
        e.set_replica("b", 70, in_sync=False)
        result = e.elect()
        assert "unclean election of 'a'" in result
        assert "20 committed record(s) lost" in result

    def test_unclean_with_no_replicas_at_all_is_refused(self):
        e = UncleanLeaderElection(committed_offset=100, allow_unclean=True)
        with pytest.raises(Invalid):
            e.elect()


class TestLossWindow:
    def test_the_loss_window_is_the_gap_below_committed(self):
        e = UncleanLeaderElection(committed_offset=100)
        e.set_replica("a", 60, in_sync=False)
        assert e.loss_window("a") == 40

    def test_a_replica_at_or_past_committed_loses_nothing(self):
        e = UncleanLeaderElection(committed_offset=100)
        e.set_replica("a", 100, in_sync=True)
        assert e.loss_window("a") == 0

    def test_an_unknown_replica_has_no_loss_window(self):
        e = UncleanLeaderElection(committed_offset=100)
        with pytest.raises(Invalid):
            e.loss_window("ghost")


class TestNote:
    def test_the_note_states_the_mode(self):
        e = UncleanLeaderElection(committed_offset=100, allow_unclean=True)
        e.set_replica("a", 100, in_sync=True)
        assert "unclean election on" in e.note()
