from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.suppression import Suppressor


class TestUpdateAndAdvance:
    def test_only_the_latest_value_per_window_is_kept(self):
        s = Suppressor(grace=10)
        s.update(window_end=100, value=1)
        s.update(window_end=100, value=2)
        s.update(window_end=100, value=3)
        # not yet past grace
        assert s.advance(stream_time=105) == []
        # past window end + grace
        assert s.advance(stream_time=110) == [(100, 3)]

    def test_absorbed_updates_are_counted(self):
        s = Suppressor(grace=0)
        s.update(100, 1)
        s.update(100, 2)
        s.update(100, 3)
        assert s.absorbed == 2

    def test_advance_releases_only_windows_past_grace(self):
        s = Suppressor(grace=10)
        s.update(100, 1)
        s.update(200, 2)
        assert s.advance(stream_time=115) == [(100, 1)]
        assert 200 in s.pending


class TestForceEmit:
    def test_emitting_within_grace_is_refused(self):
        s = Suppressor(grace=10)
        s.update(100, 5)
        with pytest.raises(Invalid) as caught:
            s.force_emit(window_end=100, stream_time=105)
        assert "still within its grace period" in str(caught.value)

    def test_emitting_after_grace_returns_the_final(self):
        s = Suppressor(grace=10)
        s.update(100, 5)
        assert s.force_emit(window_end=100, stream_time=110) == 5


class TestConfigAndSavings:
    def test_a_negative_grace_is_refused(self):
        with pytest.raises(Invalid):
            Suppressor(grace=-1)

    def test_savings_reports_absorbed_and_emitted(self):
        s = Suppressor(grace=0)
        s.update(100, 1)
        s.update(100, 2)
        s.advance(stream_time=100)
        assert "1 intermediate update(s) absorbed" in s.savings()
