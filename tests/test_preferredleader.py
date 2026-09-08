from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.preferredleader import LeadershipBalance


def lopsided() -> LeadershipBalance:
    return LeadershipBalance(
        preferred={0: "b1", 1: "b2", 2: "b3", 3: "b1"},
        current_leader={0: "b2", 1: "b2", 2: "b3", 3: "b2"},
        in_sync={
            0: {"b1", "b2"},
            1: {"b2"},
            2: {"b3"},
            3: {"b1", "b2"},
        },
    )


class TestImbalance:
    def test_the_spread_measures_the_hotspot(self):
        balance = lopsided()
        # b2 leads 0,1,3 (3), b3 leads 2 (1): spread 2
        assert balance.imbalance() == 2

    def test_the_report_names_the_melting_broker(self):
        report = lopsided().report()
        assert "spread 2" in report
        assert "b2 leads 3" in report
        assert "one broker is melting" in report


class TestRestoration:
    def test_restorable_partitions_have_caught_up_preferreds(self):
        balance = lopsided()
        assert balance.restorable() == [0, 3]

    def test_restoring_moves_leadership_to_the_preferred(self):
        balance = lopsided()
        verdict = balance.restore(0)
        assert "restored to b1" in verdict
        assert balance.current_leader[0] == "b1"

    def test_restoring_reduces_the_imbalance(self):
        balance = lopsided()
        balance.restore(0)
        balance.restore(3)
        assert balance.imbalance() < 2

    def test_a_lagging_preferred_cannot_take_leadership(self):
        balance = LeadershipBalance(
            preferred={0: "b1"},
            current_leader={0: "b2"},
            in_sync={0: {"b2"}},
        )
        with pytest.raises(Invalid) as caught:
            balance.restore(0)
        assert "would stall the partition" in str(caught.value)


class TestBalanced:
    def test_an_even_cluster_reports_no_hotspot(self):
        balance = LeadershipBalance(
            preferred={0: "b1", 1: "b2"},
            current_leader={0: "b1", 1: "b2"},
        )
        assert "no broker is a hotspot" in balance.report()
