from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.groupstate import (
    COMPLETING,
    EMPTY,
    PREPARING,
    STABLE,
    GroupStateMachine,
)


def stable_group() -> GroupStateMachine:
    g = GroupStateMachine()
    g.transition(PREPARING)
    g.transition(COMPLETING)
    g.transition(STABLE)
    return g


class TestTransitions:
    def test_the_happy_path_reaches_stable(self):
        g = stable_group()
        assert g.state == STABLE
        assert g.may_consume()

    def test_skipping_completing_is_refused(self):
        g = GroupStateMachine()
        g.transition(PREPARING)
        with pytest.raises(Invalid) as caught:
            g.transition(STABLE)
        assert "no shortcut past CompletingRebalance" in str(
            caught.value
        )

    def test_a_fresh_group_is_empty(self):
        assert GroupStateMachine().state == EMPTY

    def test_preparing_bumps_the_generation(self):
        g = GroupStateMachine()
        before = g.generation
        g.transition(PREPARING)
        assert g.generation == before + 1


class TestConsumptionGate:
    def test_consumption_is_only_stable(self):
        g = GroupStateMachine()
        assert not g.may_consume()
        g.transition(PREPARING)
        assert not g.may_consume()

    def test_a_commit_outside_stable_is_refused(self):
        g = GroupStateMachine()
        g.transition(PREPARING)
        with pytest.raises(Invalid) as caught:
            g.commit(1)
        assert "about to change" in str(caught.value)


class TestGenerationFencing:
    def test_a_current_generation_commit_is_accepted(self):
        g = stable_group()
        assert "accepted at generation 1" in g.commit(1)

    def test_a_stale_generation_commit_is_refused(self):
        g = stable_group()
        g.transition(PREPARING)
        g.transition(COMPLETING)
        g.transition(STABLE)
        with pytest.raises(Invalid) as caught:
            g.commit(1)
        assert "superseded assignment" in str(caught.value)
