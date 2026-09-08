from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.reassignmentthrottle import ReassignmentThrottle


class TestEstimate:
    def test_completion_is_bytes_over_rate(self):
        t = ReassignmentThrottle(
            bytes_to_move=1000, throttle_bytes_per_sec=100, link_capacity_bytes_per_sec=500
        )
        assert t.completion_seconds() == pytest.approx(10.0)

    def test_headroom_is_capacity_minus_throttle(self):
        t = ReassignmentThrottle(
            bytes_to_move=1000, throttle_bytes_per_sec=100, link_capacity_bytes_per_sec=500
        )
        assert t.headroom_bytes_per_sec() == pytest.approx(400.0)

    def test_a_lower_throttle_takes_longer(self):
        fast = ReassignmentThrottle(1000, 200, 500).completion_seconds()
        slow = ReassignmentThrottle(1000, 100, 500).completion_seconds()
        assert slow > fast


class TestDeadline:
    def test_the_deadline_throttle_finishes_in_time(self):
        t = ReassignmentThrottle(
            bytes_to_move=1000, throttle_bytes_per_sec=100, link_capacity_bytes_per_sec=500
        )
        rate = t.throttle_for_deadline(20)  # 1000 / 20 = 50 B/s
        assert rate == pytest.approx(50.0)

    def test_a_deadline_needing_more_than_capacity_is_refused(self):
        t = ReassignmentThrottle(
            bytes_to_move=1000, throttle_bytes_per_sec=100, link_capacity_bytes_per_sec=500
        )
        with pytest.raises(Invalid) as caught:
            t.throttle_for_deadline(1)  # needs 1000 B/s, capacity is 500
        assert "cannot both be satisfied" in str(caught.value)

    def test_a_zero_deadline_is_refused(self):
        t = ReassignmentThrottle(1000, 100, 500)
        with pytest.raises(Invalid):
            t.throttle_for_deadline(0)


class TestConfig:
    def test_a_throttle_at_capacity_is_refused(self):
        with pytest.raises(Invalid) as caught:
            ReassignmentThrottle(1000, 500, 500)
        assert "not a throttle" in str(caught.value)

    def test_a_zero_throttle_is_refused(self):
        with pytest.raises(Invalid):
            ReassignmentThrottle(1000, 0, 500)


class TestNote:
    def test_the_note_states_time_and_headroom(self):
        t = ReassignmentThrottle(1000, 100, 500)
        note = t.note()
        assert "10s" in note
        assert "400 B/s for live traffic" in note
