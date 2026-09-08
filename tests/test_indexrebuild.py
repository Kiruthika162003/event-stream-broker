from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.indexrebuild import IndexRebuilder


def _positions(end, interval):
    return {o: o * 10 for o in range(0, end) if o % interval == 0}


class TestDetect:
    def test_a_short_index_is_detected(self):
        r = IndexRebuilder(interval=4, log_end=20, entries=[(0, 0), (4, 40)])
        assert r.is_short()

    def test_a_corrupt_index_is_detected(self):
        r = IndexRebuilder(interval=4, log_end=20, entries=[(4, 40), (4, 80)])
        assert r.is_corrupt()


class TestRebuild:
    def test_a_short_index_is_extended_from_the_last_entry(self):
        r = IndexRebuilder(interval=4, log_end=20, entries=[(0, 0), (4, 40)])
        r.rebuild(_positions(20, 4))
        # entries at 0,4,8,12,16
        assert [e[0] for e in r.entries] == [0, 4, 8, 12, 16]

    def test_a_corrupt_index_is_discarded_and_rebuilt_whole(self):
        r = IndexRebuilder(interval=4, log_end=12, entries=[(4, 40), (4, 80)])
        r.rebuild(_positions(12, 4))
        assert [e[0] for e in r.entries] == [0, 4, 8]

    def test_a_log_end_below_the_index_is_refused(self):
        r = IndexRebuilder(interval=4, log_end=4, entries=[(0, 0), (8, 80)])
        with pytest.raises(Invalid) as caught:
            r.rebuild(_positions(4, 4))
        assert "truncated under the index" in str(caught.value)

    def test_a_bad_interval_is_refused(self):
        with pytest.raises(Invalid):
            IndexRebuilder(interval=0, log_end=10)


class TestReport:
    def test_the_report_compares_entries_to_the_log(self):
        r = IndexRebuilder(interval=4, log_end=20, entries=[(0, 0)])
        assert "index entry(ies) for a log of 20" in r.report()
