from __future__ import annotations

import pytest

from relay.coordinatorload import CoordinatorLoad
from relay.errors import Invalid


class TestReplay:
    def test_replay_advances_toward_the_end(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(400)
        assert load.replayed_to == 400

    def test_replay_is_clamped_to_the_end(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(5000)
        assert load.replayed_to == 1000

    def test_replay_cannot_go_backwards(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(400)
        with pytest.raises(Invalid):
            load.replay(300)


class TestReadiness:
    def test_ready_requires_replay_to_the_end(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(999)
        with pytest.raises(Invalid) as caught:
            load.mark_ready()
        assert "partial view" in str(caught.value)

    def test_full_replay_marks_ready(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(1000)
        assert "fully replayed" in load.mark_ready()


class TestServe:
    def test_serving_while_loading_forces_retry(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(600)
        with pytest.raises(Invalid) as caught:
            load.serve("fetch-offset")
        assert "load in progress" in str(caught.value)
        assert "60%" in str(caught.value)

    def test_a_ready_coordinator_serves(self):
        load = CoordinatorLoad(partition_end=1000)
        load.replay(1000)
        load.mark_ready()
        assert load.serve("commit") == "served 'commit'"


class TestFraction:
    def test_an_empty_partition_is_fully_loaded(self):
        load = CoordinatorLoad(partition_end=0)
        assert "100%" in load.fraction()
