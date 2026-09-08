from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.temporaljoin import TemporalJoin


def _join():
    t = TemporalJoin()
    t.add_version(100, "rate-A")
    t.add_version(200, "rate-B")
    t.add_version(300, "rate-C")
    return t


class TestJoin:
    def test_it_joins_the_version_current_at_the_event_time(self):
        t = _join()
        assert t.join(250) == "rate-B"

    def test_an_exact_effective_time_uses_that_version(self):
        t = _join()
        assert t.join(200) == "rate-B"

    def test_a_late_record_still_gets_the_old_version(self):
        t = _join()
        # a record from time 150 joins rate-A even though C is current
        assert t.join(150) == "rate-A"

    def test_a_record_before_the_first_version_is_missing(self):
        t = _join()
        with pytest.raises(Missing) as caught:
            t.join(50)
        assert "did not exist yet" in str(caught.value)


class TestOrdering:
    def test_versions_must_increase_in_time(self):
        t = _join()
        with pytest.raises(Invalid):
            t.add_version(150, "late")


class TestStaleness:
    def test_it_reports_how_far_back_the_version_is(self):
        t = _join()
        note = t.staleness(250)
        assert "effective 50 before the record" in note
