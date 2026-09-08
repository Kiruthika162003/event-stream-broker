from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.topn import TopN


class TestOffer:
    def test_it_keeps_the_highest_scores(self):
        t = TopN(n=3)
        for item, score in [("a", 10), ("b", 50), ("c", 30), ("d", 5), ("e", 40)]:
            t.offer(item, score)
        top = t.top()
        assert [item for item, _ in top] == ["b", "e", "c"]

    def test_a_low_score_is_rejected_when_full(self):
        t = TopN(n=2)
        t.offer("a", 100)
        t.offer("b", 90)
        assert not t.offer("c", 1)

    def test_a_high_score_displaces_the_minimum(self):
        t = TopN(n=2)
        t.offer("a", 100)
        t.offer("b", 90)
        assert t.offer("c", 95)
        assert "b" not in [item for item, _ in t.top()]


class TestThreshold:
    def test_an_unfilled_topn_admits_anything(self):
        t = TopN(n=5)
        t.offer("a", 1)
        assert "not full" in t.threshold()

    def test_a_full_topn_reports_the_threshold(self):
        t = TopN(n=2)
        t.offer("a", 100)
        t.offer("b", 90)
        assert "admission threshold 90" in t.threshold()


class TestConfig:
    def test_a_zero_n_is_refused(self):
        with pytest.raises(Invalid):
            TopN(n=0)
