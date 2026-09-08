from __future__ import annotations

import pytest

from relay.controllerepoch import ControllerFencer
from relay.errors import Fenced, Invalid


def fencer() -> ControllerFencer:
    f = ControllerFencer()
    f.take_over("b1", epoch=1)
    return f


class TestTakeover:
    def test_a_new_controller_supersedes(self):
        f = fencer()
        verdict = f.take_over("b2", epoch=2)
        assert "controller at epoch 2" in verdict
        assert f.controller == "b2"

    def test_a_non_greater_epoch_cannot_take_over(self):
        f = fencer()
        with pytest.raises(Invalid) as caught:
            f.take_over("b2", epoch=1)
        assert "must supersede, not tie" in str(caught.value)


class TestApplyChange:
    def test_a_current_epoch_change_applies(self):
        f = fencer()
        assert "applied" in f.apply_change(1, "reassign p0")

    def test_a_stale_epoch_change_is_fenced(self):
        f = fencer()
        f.take_over("b2", epoch=2)
        with pytest.raises(Fenced) as caught:
            f.apply_change(1, "reassign p0")
        assert "cluster-level split brain" in str(caught.value)
        assert f.rejected_stale == 1

    def test_a_future_epoch_means_a_missed_takeover(self):
        f = fencer()
        with pytest.raises(Invalid) as caught:
            f.apply_change(5, "reassign p0")
        assert "missed a takeover" in str(caught.value)


class TestReport:
    def test_the_report_shows_fenced_changes(self):
        f = fencer()
        f.take_over("b2", epoch=2)
        with pytest.raises(Fenced):
            f.apply_change(1, "x")
        report = f.report()
        assert "controller b2 at epoch 2" in report
        assert "1 stale change(s) fenced" in report
