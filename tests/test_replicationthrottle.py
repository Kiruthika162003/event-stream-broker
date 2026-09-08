from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.replicationthrottle import ReplicationThrottle


def throttle() -> ReplicationThrottle:
    return ReplicationThrottle(catchup_rate=100, catchup_boundary=9000)


class TestClassification:
    def test_old_fetches_are_catch_up_and_throttled(self):
        verdict = throttle().rate_for(fetch_offset=1000)
        assert "throttled at 100/tick" in verdict
        assert "leave headroom for live traffic" in verdict

    def test_tail_fetches_are_unthrottled(self):
        verdict = throttle().rate_for(fetch_offset=9500)
        assert "unthrottled" in verdict
        assert "permanently behind" in verdict

    def test_the_boundary_separates_the_two(self):
        assert throttle().is_catchup(8999)
        assert not throttle().is_catchup(9000)

    def test_a_bad_rate_is_refused(self):
        with pytest.raises(Invalid):
            ReplicationThrottle(catchup_rate=0, catchup_boundary=1)


class TestEta:
    def test_the_catchup_eta_is_computed(self):
        verdict = throttle().catchup_eta(
            follower_offset=4000, leader_offset=9500
        )
        assert "catch-up of 5000 record(s)" in verdict
        assert "finishes in about 50 tick(s)" in verdict

    def test_a_tail_follower_needs_no_catchup(self):
        verdict = throttle().catchup_eta(
            follower_offset=9200, leader_offset=9500
        )
        assert "no catch-up needed" in verdict

    def test_a_follower_ahead_of_the_leader_is_refused(self):
        with pytest.raises(Invalid):
            throttle().catchup_eta(
                follower_offset=100, leader_offset=50
            )
