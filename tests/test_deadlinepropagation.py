from __future__ import annotations

import pytest

from relay.deadlinepropagation import Deadline
from relay.errors import Invalid


class TestRemaining:
    def test_remaining_counts_down(self):
        d = Deadline(deadline_at=1000)
        assert d.remaining(now=700) == 300

    def test_expired_past_the_deadline(self):
        d = Deadline(deadline_at=1000)
        assert d.expired(now=1000)
        assert not d.expired(now=999)


class TestBeginCall:
    def test_a_call_within_budget_begins(self):
        d = Deadline(deadline_at=1000)
        assert "300 budget remaining" in d.begin_call(now=700, estimated_cost=100)

    def test_a_call_past_the_deadline_is_refused(self):
        d = Deadline(deadline_at=1000)
        with pytest.raises(Invalid) as caught:
            d.begin_call(now=1200, estimated_cost=10)
        assert "no one will read" in str(caught.value)

    def test_a_call_costing_more_than_the_budget_is_refused(self):
        d = Deadline(deadline_at=1000)
        with pytest.raises(Invalid) as caught:
            d.begin_call(now=950, estimated_cost=100)
        assert "wastes budget" in str(caught.value)


class TestHopNote:
    def test_a_hop_with_budget_reports_it(self):
        d = Deadline(deadline_at=1000)
        assert "400 of the shared deadline budget" in d.hop_note(now=600)

    def test_a_hop_with_no_budget_points_at_the_early_hops(self):
        d = Deadline(deadline_at=1000)
        assert "speed them up" in d.hop_note(now=1000)
