from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.unregisterbroker import Decommission


class TestUnregister:
    def test_a_clean_broker_unregisters(self):
        d = Decommission(broker="b3")
        assert "unregistered 'b3'" in d.unregister()

    def test_a_broker_still_leading_is_refused(self):
        d = Decommission(broker="b3", leads={"t-0", "t-1"})
        with pytest.raises(Invalid) as caught:
            d.unregister()
        assert "move leadership first" in str(caught.value)

    def test_a_broker_still_hosting_needed_replicas_is_refused(self):
        d = Decommission(broker="b3", hosts_needed={"t-5"})
        with pytest.raises(Invalid) as caught:
            d.unregister()
        assert "drops below its replication factor" in str(caught.value)


class TestProgress:
    def test_moving_leadership_and_rehoming_unblocks(self):
        d = Decommission(broker="b3", leads={"t-0"}, hosts_needed={"t-5"})
        assert not d.can_unregister()
        d.leadership_moved("t-0")
        d.replica_rehomed("t-5")
        assert d.can_unregister()
        assert "unregistered 'b3'" in d.unregister()


class TestBlockers:
    def test_blockers_names_what_remains(self):
        d = Decommission(broker="b3", leads={"t-0"})
        note = d.blockers()
        assert "leads ['t-0']" in note
        assert "reassignment still catching up" in note

    def test_a_clean_broker_reports_safe(self):
        assert "safe to unregister" in Decommission(broker="b3").blockers()
