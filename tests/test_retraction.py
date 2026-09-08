from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.retraction import RetractingEmitter


class TestEmit:
    def test_a_first_emit_is_just_an_add(self):
        e = RetractingEmitter()
        assert e.emit(window=100, value=5) == [("add", 100, 5)]

    def test_an_update_retracts_the_old_then_adds_the_new(self):
        e = RetractingEmitter()
        e.emit(100, 5)
        out = e.emit(100, 8)
        assert out == [("retract", 100, 5), ("add", 100, 8)]

    def test_the_net_effect_is_the_correction(self):
        e = RetractingEmitter()
        records = e.emit(100, 5)
        records += e.emit(100, 8)
        # a retraction-aware downstream ends at 8: +5 -5 +8
        assert e.net_effect(records) == 8


class TestRetractOnly:
    def test_retracting_an_emitted_window_undoes_it(self):
        e = RetractingEmitter()
        e.emit(100, 5)
        assert e.retract_only(100) == ("retract", 100, 5)

    def test_retracting_an_unemitted_window_is_refused(self):
        e = RetractingEmitter()
        with pytest.raises(Invalid) as caught:
            e.retract_only(100)
        assert "never emitted" in str(caught.value)


class TestReport:
    def test_report_counts_retractions(self):
        e = RetractingEmitter()
        e.emit(100, 5)
        e.emit(100, 8)
        assert "1 retraction(s) emitted" in e.report()
