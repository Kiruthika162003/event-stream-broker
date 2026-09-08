from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.smt import SmtChain


def _rename(old, new):
    def t(rec):
        if old in rec:
            rec = dict(rec)
            rec[new] = rec.pop(old)
        return rec
    return t


def _keep_if(pred):
    return lambda rec: rec if pred(rec) else None


class TestApply:
    def test_a_chain_transforms_in_order(self):
        chain = SmtChain(transforms=[_rename("a", "b")])
        assert chain.apply({"a": 1}) == {"b": 1}

    def test_a_transform_returning_none_drops_the_record(self):
        chain = SmtChain(transforms=[_keep_if(lambda r: r.get("keep"))])
        assert chain.apply({"keep": False}) is None
        assert chain.dropped == 1

    def test_a_drop_stops_the_chain(self):
        seen = []

        def record_then_pass(rec):
            seen.append(rec)
            return rec

        chain = SmtChain(transforms=[_keep_if(lambda _r: False), record_then_pass])
        chain.apply({"x": 1})
        # the second transform never ran because the first dropped
        assert seen == []


class TestBatch:
    def test_batch_filters_dropped_records(self):
        chain = SmtChain(transforms=[_keep_if(lambda r: r["v"] > 0)])
        out = chain.apply_batch([{"v": 1}, {"v": -1}, {"v": 2}])
        assert out == [{"v": 1}, {"v": 2}]


class TestConfigAndReport:
    def test_an_empty_chain_is_refused(self):
        with pytest.raises(Invalid):
            SmtChain(transforms=[])

    def test_report_counts_transformed_and_dropped(self):
        chain = SmtChain(transforms=[_keep_if(lambda r: r["v"] > 0)])
        chain.apply_batch([{"v": 1}, {"v": -1}])
        assert "1 transformed, 1 dropped (50%)" in chain.report()
