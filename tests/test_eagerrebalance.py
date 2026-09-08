from __future__ import annotations

import pytest

from relay.eagerrebalance import EagerRebalance
from relay.errors import Invalid


class TestRevoked:
    def test_eager_revokes_everything(self):
        r = EagerRebalance(total_partitions=100, moved_partitions=4)
        assert r.revoked() == 100

    def test_paused_for_nothing_is_the_unchanged_partitions(self):
        r = EagerRebalance(total_partitions=100, moved_partitions=4)
        assert r.paused_for_nothing() == 96


class TestRefusals:
    def test_more_moved_than_total_is_refused(self):
        with pytest.raises(Invalid) as caught:
            EagerRebalance(total_partitions=10, moved_partitions=20)
        assert "more partitions moved than exist" in str(caught.value)

    def test_negative_counts_are_refused(self):
        with pytest.raises(Invalid):
            EagerRebalance(total_partitions=-1, moved_partitions=0)


class TestRatio:
    def test_a_stable_group_wastes_almost_everything(self):
        r = EagerRebalance(total_partitions=100, moved_partitions=1)
        assert r.unnecessary_ratio() == 0.99

    def test_the_report_flags_the_cooperative_candidate(self):
        r = EagerRebalance(total_partitions=100, moved_partitions=4)
        note = r.report()
        assert "96 partition(s) paused for nothing (96%)" in note
        assert "candidate for cooperative" in note

    def test_an_empty_group_has_a_zero_ratio(self):
        r = EagerRebalance(total_partitions=0, moved_partitions=0)
        assert r.unnecessary_ratio() == 0.0
