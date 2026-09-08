from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rackspread import RackDistribution


class TestTolerance:
    def test_three_racks_survive_one_failure(self):
        d = RackDistribution(
            {"ra": 1, "rb": 1, "rc": 1}, min_in_sync=2
        )
        assert d.survivable_rack_failures() == 1

    def test_a_majority_in_one_rack_survives_zero(self):
        d = RackDistribution({"ra": 2, "rb": 1}, min_in_sync=2)
        assert d.survivable_rack_failures() == 0

    def test_more_racks_raise_tolerance(self):
        d = RackDistribution(
            {"ra": 1, "rb": 1, "rc": 1, "rd": 1, "re": 1},
            min_in_sync=2,
        )
        assert d.survivable_rack_failures() == 3


class TestReport:
    def test_the_report_names_the_heaviest_rack(self):
        d = RackDistribution(
            {"ra": 1, "rb": 1, "rc": 1}, min_in_sync=2
        )
        report = d.report()
        assert "3 rack(s)" in report
        assert "survives 1 rack failure(s)" in report

    def test_zero_tolerance_gets_the_false_comfort_warning(self):
        d = RackDistribution({"ra": 2, "rb": 1}, min_in_sync=2)
        report = d.report()
        assert "survives 0 rack failure(s)" in report
        assert "the false comfort exposed before the event" in (
            report
        )


class TestRefusals:
    def test_no_replicas_is_refused(self):
        with pytest.raises(Invalid):
            RackDistribution({}, min_in_sync=1)

    def test_a_bad_min_insync_is_refused(self):
        with pytest.raises(Invalid):
            RackDistribution({"ra": 1}, min_in_sync=0)
