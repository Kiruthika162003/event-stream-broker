from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.punctuate import STREAM_TIME, WALL_CLOCK, Punctuation


class TestStreamTime:
    def test_it_fires_as_stream_time_advances(self):
        p = Punctuation(clock=STREAM_TIME, interval=10)
        assert p.on_stream_time(25) == 2  # marks at 10 and 20
        assert p.fires == 2

    def test_a_quiet_stream_does_not_fire(self):
        p = Punctuation(clock=STREAM_TIME, interval=10)
        # no records advance stream time; a wall-clock tick does nothing
        assert p.on_wall_clock(1000) == 0
        assert p.fires == 0

    def test_the_idle_note_shows_the_drift(self):
        p = Punctuation(clock=STREAM_TIME, interval=10)
        p.on_stream_time(10)
        note = p.idle_note(stream_time=10, wall_clock=5000)
        assert "gap of 4990" in note
        assert "silently stopped" in note


class TestWallClock:
    def test_it_fires_on_real_time_even_when_idle(self):
        p = Punctuation(clock=WALL_CLOCK, interval=60)
        assert p.on_wall_clock(180) == 3
        assert p.on_stream_time(9999) == 0  # stream time is irrelevant

    def test_the_idle_note_is_reassuring(self):
        p = Punctuation(clock=WALL_CLOCK, interval=60)
        assert "fires on schedule even when idle" in p.idle_note(0, 0)


class TestConfig:
    def test_an_unknown_clock_is_refused(self):
        with pytest.raises(Invalid):
            Punctuation(clock="cpu-time", interval=10)

    def test_a_non_positive_interval_is_refused(self):
        with pytest.raises(Invalid):
            Punctuation(clock=STREAM_TIME, interval=0)
