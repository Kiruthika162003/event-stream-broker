from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupcoordinatorload import CoordinatorLoad


class TestLoading:
    def test_a_fresh_coordinator_is_loading(self):
        c = CoordinatorLoad(log_end=100)
        assert not c.is_loaded()

    def test_a_request_while_loading_is_refused(self):
        c = CoordinatorLoad(log_end=100)
        c.apply(40)
        with pytest.raises(Invalid) as caught:
            c.serve("fetch-offset")
        assert "coordinator loading" in str(caught.value)

    def test_replay_reaching_the_end_flips_to_loaded(self):
        c = CoordinatorLoad(log_end=100)
        c.apply(100)
        assert c.is_loaded()
        assert "served" in c.serve("fetch-offset")

    def test_an_empty_partition_is_loaded_immediately(self):
        c = CoordinatorLoad(log_end=0)
        assert c.is_loaded()
        assert "served" in c.serve("commit")


class TestApply:
    def test_replay_accumulates(self):
        c = CoordinatorLoad(log_end=100)
        c.apply(30)
        c.apply(30)
        assert c.replayed_to == 60

    def test_replaying_past_the_end_is_refused(self):
        c = CoordinatorLoad(log_end=100)
        c.apply(90)
        with pytest.raises(Invalid) as caught:
            c.apply(20)
        assert "invent group state" in str(caught.value)

    def test_a_negative_replay_is_refused(self):
        c = CoordinatorLoad(log_end=100)
        with pytest.raises(Invalid):
            c.apply(-5)


class TestProgress:
    def test_progress_is_the_fraction_applied(self):
        c = CoordinatorLoad(log_end=200)
        c.apply(50)
        assert c.progress() == pytest.approx(0.25)

    def test_the_note_states_loading_and_percent(self):
        c = CoordinatorLoad(log_end=100)
        c.apply(25)
        note = c.note()
        assert "loading" in note
        assert "25%" in note
