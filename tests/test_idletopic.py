from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.idletopic import IdleDetector, TopicActivity


def detector() -> IdleDetector:
    return IdleDetector(idle_window=1000)


class TestAssessment:
    def test_no_produces_no_consumers_marks_for_review(self):
        activity = TopicActivity("stale", last_produce_tick=0, active_consumers=0)
        verdict = detector().assess(activity, now=5000)
        assert "mark for review, never auto-delete" in verdict
        assert "may fire monthly" in verdict

    def test_no_produces_but_consumers_is_being_drained(self):
        activity = TopicActivity("draining", last_produce_tick=0, active_consumers=3)
        verdict = detector().assess(activity, now=5000)
        assert "being drained, not abandoned" in verdict

    def test_produces_but_no_consumers_is_a_dead_reader(self):
        activity = TopicActivity("orphan", last_produce_tick=4900, active_consumers=0)
        verdict = detector().assess(activity, now=5000)
        assert "reader died, a different problem" in verdict

    def test_active_on_both_is_healthy(self):
        activity = TopicActivity("live", last_produce_tick=4900, active_consumers=2)
        assert "active on both signals" in detector().assess(
            activity, now=5000
        )


class TestArchivable:
    def test_only_both_signals_make_a_topic_archivable(self):
        d = detector()
        dead = TopicActivity("dead", last_produce_tick=0, active_consumers=0)
        drained = TopicActivity("drain", last_produce_tick=0, active_consumers=1)
        assert d.archivable(dead, now=5000)
        assert not d.archivable(drained, now=5000)

    def test_a_bad_window_is_refused(self):
        with pytest.raises(Invalid):
            IdleDetector(idle_window=0)
