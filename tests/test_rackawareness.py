from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rackawareness import RackAwarePlacement


def _cluster(layout: dict[str, list[str]]) -> RackAwarePlacement:
    p = RackAwarePlacement()
    for rack, brokers in layout.items():
        for b in brokers:
            p.add_broker(b, rack)
    return p


class TestSpread:
    def test_replicas_land_in_distinct_racks_when_racks_suffice(self):
        p = _cluster({"r1": ["b1"], "r2": ["b2"], "r3": ["b3"]})
        chosen = p.place(3)
        assert p.rack_span(chosen) == 3

    def test_the_first_broker_is_the_preferred_leader(self):
        p = _cluster({"r1": ["b1"], "r2": ["b2"]})
        chosen = p.place(2)
        assert len(chosen) == 2
        # leader and follower are in different racks
        assert p.racks[chosen[0]] != p.racks[chosen[1]]

    def test_fewer_racks_than_replicas_spreads_as_evenly_as_it_can(self):
        # two racks, three replicas: span two, not one
        p = _cluster({"r1": ["b1", "b3"], "r2": ["b2"]})
        chosen = p.place(3)
        assert p.rack_span(chosen) == 2

    def test_replicas_alternate_racks_before_repeating(self):
        p = _cluster({"r1": ["a1", "a2"], "r2": ["b1", "b2"]})
        chosen = p.place(3)
        # first two must be in different racks
        assert p.racks[chosen[0]] != p.racks[chosen[1]]


class TestRefusals:
    def test_a_factor_above_broker_count_is_refused(self):
        p = _cluster({"r1": ["b1"], "r2": ["b2"]})
        with pytest.raises(Invalid) as caught:
            p.place(3)
        assert "exceeds" in str(caught.value)

    def test_a_broker_without_a_rack_is_refused(self):
        p = RackAwarePlacement()
        with pytest.raises(Invalid) as caught:
            p.add_broker("b1", "")
        assert "no rack assigned" in str(caught.value)

    def test_a_zero_factor_is_refused(self):
        p = _cluster({"r1": ["b1"]})
        with pytest.raises(Invalid):
            p.place(0)


class TestNote:
    def test_a_single_rack_span_is_flagged(self):
        p = _cluster({"r1": ["b1", "b2", "b3"]})
        assert "span of one" in p.note(2)

    def test_a_healthy_span_is_reported(self):
        p = _cluster({"r1": ["b1"], "r2": ["b2"], "r3": ["b3"]})
        assert "span 3 rack" in p.note(3)
