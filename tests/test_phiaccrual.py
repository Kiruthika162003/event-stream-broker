from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.phiaccrual import PhiAccrual


def _detector():
    d = PhiAccrual(threshold=3.0)
    # heartbeats every 10 ticks -> mean interval 10
    for t in (0, 10, 20, 30):
        d.heartbeat(t)
    return d


class TestPhi:
    def test_phi_is_low_just_after_a_beat(self):
        d = _detector()
        assert d.phi(now=35) == 0.5  # 5/10
        assert not d.is_suspect(now=35)

    def test_phi_rises_with_silence(self):
        d = _detector()
        assert d.phi(now=60) == 3.0  # 30/10
        assert d.is_suspect(now=60)

    def test_phi_before_any_interval_is_refused(self):
        d = PhiAccrual(threshold=3.0)
        d.heartbeat(0)  # only one beat, no interval
        with pytest.raises(Invalid):
            d.phi(now=5)


class TestAdaptation:
    def test_a_slow_beater_is_less_suspicious_at_the_same_gap(self):
        fast = PhiAccrual(threshold=3.0)
        for t in (0, 1, 2, 3):
            fast.heartbeat(t)  # mean 1
        slow = PhiAccrual(threshold=3.0)
        for t in (0, 10, 20, 30):
            slow.heartbeat(t)  # mean 10
        # same 5-tick gap: fast is far more suspicious
        assert fast.phi(now=35) > slow.phi(now=35)


class TestConfig:
    def test_a_non_positive_threshold_is_refused(self):
        with pytest.raises(Invalid):
            PhiAccrual(threshold=0)


class TestReport:
    def test_report_names_the_state(self):
        d = _detector()
        assert "SUSPECT" in d.report(now=60)
        assert "alive" in d.report(now=32)
