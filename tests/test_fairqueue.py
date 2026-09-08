from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fairqueue import FairQueue


class TestFairness:
    def test_a_heavier_client_gets_more_service(self):
        fq = FairQueue(weights={"big": 2, "small": 1})
        # both flood their queues
        for _ in range(100):
            fq.enqueue("big", 1)
            fq.enqueue("small", 1)
        for _ in range(30):
            fq.round()
        # big served about twice small
        assert fq.served["big"] == 2 * fq.served["small"]

    def test_a_flood_does_not_starve_another_client(self):
        fq = FairQueue(weights={"flood": 1, "quiet": 1})
        for _ in range(1000):
            fq.enqueue("flood", 1)
        for _ in range(5):
            fq.enqueue("quiet", 1)
        for _ in range(10):
            fq.round()
        # quiet's 5 requests are all served despite the flood
        assert fq.served["quiet"] == 5


class TestDeficit:
    def test_leftover_deficit_carries(self):
        fq = FairQueue(weights={"c": 1})
        fq.enqueue("c", 3)  # costs 3, one round gives deficit 1
        fq.round()
        assert fq.served["c"] == 0  # not enough deficit yet
        fq.round()
        fq.round()
        assert fq.served["c"] == 3  # deficit reached 3


class TestConfig:
    def test_a_zero_weight_is_refused(self):
        with pytest.raises(Invalid):
            FairQueue(weights={"c": 0})

    def test_enqueue_to_an_unknown_client_is_refused(self):
        fq = FairQueue(weights={"c": 1})
        with pytest.raises(Invalid):
            fq.enqueue("other", 1)


class TestReport:
    def test_report_names_served_and_weight(self):
        fq = FairQueue(weights={"c": 3})
        assert "weight 3" in fq.report()
