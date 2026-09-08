from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.isrflap import FlapDetector, ReplicaFlapHistory


def flapper() -> ReplicaFlapHistory:
    h = ReplicaFlapHistory("f1")
    state = True
    for tick in range(0, 60, 10):
        h.record(tick, state)
        state = not state
    return h


def steady_out() -> ReplicaFlapHistory:
    h = ReplicaFlapHistory("f2")
    h.record(0, True)
    h.record(5, False)
    return h


def detector() -> FlapDetector:
    return FlapDetector(window=100, flap_threshold=4, cooldown=50)


class TestDetection:
    def test_a_flapper_crosses_the_threshold(self):
        assert detector().is_flapping(flapper(), now=60)

    def test_a_steady_out_replica_is_not_flapping(self):
        assert not detector().is_flapping(steady_out(), now=60)

    def test_only_repeated_transitions_are_recorded(self):
        h = ReplicaFlapHistory("f")
        h.record(0, True)
        h.record(10, True)
        assert len(h.transitions) == 1

    def test_a_threshold_below_two_is_refused(self):
        with pytest.raises(Invalid):
            FlapDetector(window=100, flap_threshold=1, cooldown=1)


class TestRejoin:
    def test_a_flapper_is_held_out_even_when_qualified(self):
        verdict = detector().may_rejoin(
            flapper(), now=60, currently_qualifies=True
        )
        assert "held out for cool-down" in verdict
        assert "trades a stable set for a churning one" in verdict

    def test_a_stable_replica_may_rejoin(self):
        verdict = detector().may_rejoin(
            steady_out(), now=200, currently_qualifies=True
        )
        assert "may rejoin" in verdict

    def test_a_non_qualifying_replica_stays_out(self):
        verdict = detector().may_rejoin(
            flapper(), now=60, currently_qualifies=False
        )
        assert "does not currently qualify" in verdict


class TestClassification:
    def test_flappers_get_a_different_diagnosis(self):
        verdict = detector().classify(
            [flapper(), steady_out()], now=60
        )
        assert "1 flapper(s) (f1)" in verdict
        assert "sick disk or saturated link" in verdict

    def test_clean_departures_report_calm(self):
        verdict = detector().classify([steady_out()], now=60)
        assert "left cleanly" in verdict
