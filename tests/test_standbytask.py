from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.standbytask import StandbyManager


class TestTrack:
    def test_lag_is_the_gap_to_the_changelog_end(self):
        m = StandbyManager(changelog_end=1000)
        m.track("i1", standby_offset=950)
        assert m.lag_of("i1") == 50

    def test_an_offset_past_the_end_is_refused(self):
        m = StandbyManager(changelog_end=1000)
        with pytest.raises(Invalid) as caught:
            m.track("i1", standby_offset=1500)
        assert "impossible reading" in str(caught.value)


class TestPromote:
    def test_the_least_lagged_standby_is_promoted(self):
        m = StandbyManager(changelog_end=1000)
        m.track("i1", standby_offset=800)
        m.track("i2", standby_offset=990)
        note = m.promote_best()
        assert "promote i2" in note
        assert "replays only 10 record(s)" in note

    def test_no_standby_refuses_promotion(self):
        m = StandbyManager(changelog_end=1000)
        with pytest.raises(Invalid) as caught:
            m.promote_best()
        assert "rebuild from cold" in str(caught.value)

    def test_lag_of_an_untracked_instance_is_refused(self):
        m = StandbyManager(changelog_end=1000)
        with pytest.raises(Invalid):
            m.lag_of("ghost")


class TestFailoverCost:
    def test_the_cost_is_the_best_standby_lag(self):
        m = StandbyManager(changelog_end=1000)
        m.track("i1", standby_offset=990)
        assert "best standby lag 10" in m.failover_cost()

    def test_no_standby_means_a_cold_replay(self):
        m = StandbyManager(changelog_end=1000)
        assert "cold" in m.failover_cost()
