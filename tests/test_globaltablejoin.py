from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.globaltablejoin import INNER, LEFT, GlobalTableJoin


def _join(join_type=INNER):
    return GlobalTableJoin(
        table={"c1": "Alice", "c2": "Bob"},
        foreign_key=lambda r: r["customer"],
        join_type=join_type,
    )


class TestJoin:
    def test_a_match_enriches_the_record(self):
        j = _join()
        assert j.join({"customer": "c1"})["enriched"] == "Alice"

    def test_an_inner_join_drops_a_miss(self):
        j = _join(INNER)
        assert j.join({"customer": "c9"}) is None

    def test_a_left_join_null_enriches_a_miss(self):
        j = _join(LEFT)
        assert j.join({"customer": "c9"})["enriched"] is None

    def test_an_unknown_join_type_is_refused(self):
        with pytest.raises(Invalid):
            GlobalTableJoin(table={}, foreign_key=lambda r: r["k"], join_type="outer")


class TestBatch:
    def test_batch_drops_inner_misses(self):
        j = _join(INNER)
        out = j.join_batch([{"customer": "c1"}, {"customer": "c9"}, {"customer": "c2"}])
        assert [r["enriched"] for r in out] == ["Alice", "Bob"]


class TestMissRate:
    def test_it_reports_the_miss_rate(self):
        j = _join(LEFT)
        j.join({"customer": "c1"})
        j.join({"customer": "c9"})
        note = j.miss_rate()
        assert "1/2 missed the table (50%)" in note
