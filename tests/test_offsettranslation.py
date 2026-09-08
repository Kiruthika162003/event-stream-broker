from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.offsettranslation import OffsetTranslator


def _t():
    t = OffsetTranslator()
    t.add_checkpoint(100, 40)
    t.add_checkpoint(200, 130)
    t.add_checkpoint(300, 225)
    return t


class TestTranslate:
    def test_an_exact_checkpoint_translates(self):
        assert _t().translate(200) == 130

    def test_a_between_offset_uses_the_floor_checkpoint(self):
        assert _t().translate(250) == 130

    def test_an_offset_before_the_earliest_is_refused(self):
        with pytest.raises(Missing) as caught:
            _t().translate(50)
        assert "reset on the target" in str(caught.value)


class TestCheckpoints:
    def test_a_non_monotonic_source_is_refused(self):
        t = OffsetTranslator()
        t.add_checkpoint(100, 40)
        with pytest.raises(Invalid) as caught:
            t.add_checkpoint(90, 50)
        assert "increase in both offsets" in str(caught.value)

    def test_a_non_monotonic_target_is_refused(self):
        t = OffsetTranslator()
        t.add_checkpoint(100, 40)
        with pytest.raises(Invalid):
            t.add_checkpoint(200, 30)


class TestReprocessing:
    def test_it_reports_the_gap_to_the_checkpoint(self):
        note = _t().reprocessing(250)
        assert "checkpoint at source 200 reprocesses 50 record(s)" in note
        assert "at-least-once across the failover" in note
