from __future__ import annotations

import pytest

from relay.connectoroffset import ConnectorOffsets
from relay.errors import Invalid


class TestCommit:
    def test_it_commits_the_acknowledged_prefix(self):
        c = ConnectorOffsets()
        c.read(10)
        c.read(20)
        c.read(30)
        c.acknowledge(10)
        c.acknowledge(20)
        # 30 not acked; commit stops at 20
        assert c.commit() == 20

    def test_it_does_not_commit_past_an_unacked_record(self):
        c = ConnectorOffsets()
        c.read(10)
        c.read(20)
        c.acknowledge(20)  # 10 still unacked
        # cannot commit 20 because 10 before it is not acked
        assert c.commit() == -1

    def test_resume_uses_the_committed_position(self):
        c = ConnectorOffsets()
        c.read(10)
        c.acknowledge(10)
        c.commit()
        assert c.resume_from() == 10


class TestRefusals:
    def test_a_non_advancing_read_is_refused(self):
        c = ConnectorOffsets()
        c.read(10)
        with pytest.raises(Invalid) as caught:
            c.read(5)
        assert "only move" in str(caught.value)

    def test_acking_an_unknown_position_is_refused(self):
        c = ConnectorOffsets()
        with pytest.raises(Invalid):
            c.acknowledge(99)


class TestReport:
    def test_report_shows_the_in_flight_gap(self):
        c = ConnectorOffsets()
        c.read(10)
        c.read(20)
        c.acknowledge(10)
        c.commit()
        assert "committed source position 10, latest read 20" in c.report()
