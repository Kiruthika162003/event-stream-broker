from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.rollingrestart import RollingRestart


def _rr():
    return RollingRestart(brokers=["b1", "b2", "b3"])


class TestRestart:
    def test_restarts_proceed_when_in_sync(self):
        rr = _rr()
        assert "restarted 'b1'" in rr.restart("b1")
        assert "restarted 'b2'" in rr.restart("b2")

    def test_restart_is_blocked_while_under_replicated(self):
        rr = _rr()
        rr.restart("b1")
        rr.mark_under_replicated("t-0")
        with pytest.raises(Invalid) as caught:
            rr.restart("b2")
        assert "wait for them" in str(caught.value)

    def test_restart_resumes_after_catch_up(self):
        rr = _rr()
        rr.restart("b1")
        rr.mark_under_replicated("t-0")
        rr.catch_up("t-0")
        assert "restarted 'b2'" in rr.restart("b2")

    def test_restarting_the_same_broker_twice_is_refused(self):
        rr = _rr()
        rr.restart("b1")
        with pytest.raises(Invalid) as caught:
            rr.restart("b1")
        assert "already restarted" in str(caught.value)

    def test_an_unknown_broker_is_refused(self):
        with pytest.raises(Invalid):
            _rr().restart("ghost")


class TestProgress:
    def test_progress_reports_done_and_safety(self):
        rr = _rr()
        rr.restart("b1")
        assert "1/3 brokers restarted; safe to proceed" in rr.progress()

    def test_progress_names_the_wait(self):
        rr = _rr()
        rr.restart("b1")
        rr.mark_under_replicated("t-9")
        assert "waiting on ['t-9']" in rr.progress()
